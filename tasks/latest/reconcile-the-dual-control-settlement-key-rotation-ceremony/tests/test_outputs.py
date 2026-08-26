import base64
import gc
import hashlib
import json
import os
import secrets
import struct
import subprocess
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import PyKCS11
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.keywrap import aes_key_unwrap
from cryptography.x509.oid import NameOID

ROOT = Path("/app")
DEFAULT_POLICY_PATH = ROOT / "ceremony" / "policy.json"
DEFAULT_OUTPUT = ROOT / "ceremony" / "rotation-attestation.json"
PROVISIONER = ROOT / "bin" / "rotate_ceremony"
MODULE = "/usr/lib/softhsm/libsofthsm2.so"
ENV = {**os.environ, "SOFTHSM2_CONF": "/app/ceremony/softhsm2.conf"}
os.environ["SOFTHSM2_CONF"] = ENV["SOFTHSM2_CONF"]
LIBRARY = None

ATTESTATION_KEYS = {
    "schema",
    "primary_token_label",
    "escrow_token_label",
    "epoch",
    "retiring_key_id",
    "active_key_id",
    "recovery_key_id",
    "escrow_key_id",
    "envelope_object_id",
    "continuity_object_id",
    "receipt_object_id",
    "retiring_certificate_sha256",
    "active_certificate_sha256",
    "escrow_certificate_sha256",
    "recovery_envelope_sha256",
    "continuity_payload_sha256",
    "receipt_payload_sha256",
    "continuity_signature_base64",
    "escrow_receipt_signature_base64",
}


def run(*args, check=True):
    result = subprocess.run(args, text=True, capture_output=True, env=ENV, timeout=90)
    if check and result.returncode:
        raise AssertionError(f"command failed: {' '.join(map(str, args))}\n{result.stderr}\n{result.stdout}")
    return result


def pkcs11_library():
    global LIBRARY
    if LIBRARY is None:
        LIBRARY = PyKCS11.PyKCS11Lib()
        LIBRARY.load(MODULE)
    return LIBRARY


def reload_pkcs11_library():
    global LIBRARY
    LIBRARY = None
    gc.collect()


def token_slot(library, label):
    slots = [slot for slot in library.getSlotList(tokenPresent=True) if library.getTokenInfo(slot).label.strip() == label]
    assert len(slots) == 1, f"expected one token named {label!r}, found {len(slots)}"
    return slots[0]


@contextmanager
def token_session(policy, token_kind="primary", login=True, rw=False):
    token = policy[f"{token_kind}_token"]
    library = pkcs11_library()
    flags = PyKCS11.CKF_SERIAL_SESSION | (PyKCS11.CKF_RW_SESSION if rw else 0)
    session = library.openSession(token_slot(library, token["label"]), flags)
    logged_in = False
    try:
        if login:
            session.login(token["user_pin"])
            logged_in = True
        yield session
    finally:
        if logged_in:
            try:
                session.logout()
            except PyKCS11.PyKCS11Error:
                pass
        session.closeSession()


def raw_bytes(value):
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    return bytes(value)


def find_one(session, object_class, identifier, *, object_id=False):
    attribute = PyKCS11.CKA_OBJECT_ID if object_id else PyKCS11.CKA_ID
    handles = session.findObjects([(PyKCS11.CKA_CLASS, object_class), (attribute, bytes.fromhex(identifier))])
    assert len(handles) == 1
    return handles[0]


def certificate_der(session, identifier):
    handle = find_one(session, PyKCS11.CKO_CERTIFICATE, identifier)
    private, value = session.getAttributeValue(handle, [PyKCS11.CKA_PRIVATE, PyKCS11.CKA_VALUE])
    assert private is False
    return raw_bytes(value)


def evidence_value(session, policy, name):
    handle = find_one(session, PyKCS11.CKO_DATA, policy[name]["object_id"], object_id=True)
    private, label, application, value = session.getAttributeValue(
        handle,
        [PyKCS11.CKA_PRIVATE, PyKCS11.CKA_LABEL, PyKCS11.CKA_APPLICATION, PyKCS11.CKA_VALUE],
    )
    assert private is False
    assert label == policy[name]["label"]
    assert application == policy[name]["application"]
    return raw_bytes(value)


def verify_pkcs1(certificate_der_bytes, signature, payload):
    certificate = x509.load_der_x509_certificate(certificate_der_bytes)
    certificate.public_key().verify(signature, payload, padding.PKCS1v15(), hashes.SHA256())


def envelope_aad(policy, active_digest):
    return (
        "settlement-recovery-envelope-v2\n"
        f"epoch={policy['epoch']}\n"
        f"primary_token_label={policy['primary_token']['label']}\n"
        f"escrow_token_label={policy['escrow_token']['label']}\n"
        f"active_key_id={policy['active']['id']}\n"
        f"recovery_key_id={policy['recovery']['id']}\n"
        f"escrow_key_id={policy['escrow']['id']}\n"
        f"active_certificate_sha256={active_digest}\n"
    ).encode()


def continuity_payload(policy, active_digest, envelope_digest):
    return (
        "settlement-rotation-continuity-v2\n"
        f"epoch={policy['epoch']}\n"
        f"retiring_key_id={policy['retiring']['id']}\n"
        f"active_key_id={policy['active']['id']}\n"
        f"active_certificate_sha256={active_digest}\n"
        f"recovery_envelope_sha256={envelope_digest}\n"
    ).encode()


def receipt_payload(policy, continuity_digest, envelope_digest):
    return (
        "settlement-escrow-receipt-v2\n"
        f"epoch={policy['epoch']}\n"
        f"primary_token_label={policy['primary_token']['label']}\n"
        f"escrow_token_label={policy['escrow_token']['label']}\n"
        f"escrow_key_id={policy['escrow']['id']}\n"
        f"continuity_signature_sha256={continuity_digest}\n"
        f"recovery_envelope_sha256={envelope_digest}\n"
    ).encode()


def canonical_envelope(value):
    return (json.dumps(value, ensure_ascii=True, separators=(",", ":")) + "\n").encode()


def decrypt_oaep(policy, wrapped):
    with tempfile.TemporaryDirectory(prefix="verifier-escrow-") as directory:
        wrapped_path = Path(directory) / "wrapped.bin"
        clear_path = Path(directory) / "clear.bin"
        wrapped_path.write_bytes(wrapped)
        result = run(
            "pkcs11-tool",
            "--module",
            MODULE,
            "--token-label",
            policy["escrow_token"]["label"],
            "--login",
            "--pin",
            policy["escrow_token"]["user_pin"],
            "--decrypt",
            "--mechanism",
            "RSA-PKCS-OAEP",
            "--hash-algorithm",
            "SHA-1",
            "--mgf",
            "MGF1-SHA1",
            "--id",
            policy["escrow"]["id"],
            "--input-file",
            str(wrapped_path),
            "--output-file",
            str(clear_path),
            check=False,
        )
        assert result.returncode == 0, result.stderr
        clear = clear_path.read_bytes()
        clear_path.write_bytes(b"\0" * len(clear))
        return clear


def decode_envelope(policy, envelope, active_der):
    value = json.loads(envelope)
    assert list(value) == [
        "schema",
        "aad_sha256",
        "nonce_base64",
        "wrapped_recovery_key_base64",
        "encrypted_private_key_base64",
    ]
    assert canonical_envelope(value) == envelope
    assert value["schema"] == "settlement-recovery-envelope-v2"
    aad = envelope_aad(policy, hashlib.sha256(active_der).hexdigest())
    assert value["aad_sha256"] == hashlib.sha256(aad).hexdigest()
    nonce = base64.b64decode(value["nonce_base64"], validate=True)
    wrapped = base64.b64decode(value["wrapped_recovery_key_base64"], validate=True)
    encrypted = base64.b64decode(value["encrypted_private_key_base64"], validate=True)
    assert len(nonce) == 12
    recovery_key = decrypt_oaep(policy, wrapped)
    assert len(recovery_key) == 32
    private_der = AESGCM(recovery_key).decrypt(nonce, encrypted, aad)
    active_key = serialization.load_der_private_key(private_der, password=None)
    assert private_der == active_key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    assert active_key.public_key().public_numbers() == x509.load_der_x509_certificate(active_der).public_key().public_numbers()
    return recovery_key, active_key, aad


def allowed_mechanisms(value):
    raw = raw_bytes(value)
    assert len(raw) % 8 == 0
    return tuple(struct.unpack("<Q", raw[offset : offset + 8])[0] for offset in range(0, len(raw), 8))


def wrap_probe(session, policy, recovery_key, envelope_digest):
    recovery = find_one(session, PyKCS11.CKO_SECRET_KEY, policy["recovery"]["id"])
    probe_value = hashlib.sha256(b"settlement-recovery-probe-v2\n" + bytes.fromhex(envelope_digest)).digest()[:16]
    probe = session.createObject(
        [
            (PyKCS11.CKA_CLASS, PyKCS11.CKO_SECRET_KEY),
            (PyKCS11.CKA_KEY_TYPE, PyKCS11.CKK_AES),
            (PyKCS11.CKA_TOKEN, False),
            (PyKCS11.CKA_PRIVATE, True),
            (PyKCS11.CKA_SENSITIVE, False),
            (PyKCS11.CKA_EXTRACTABLE, True),
            (PyKCS11.CKA_VALUE, list(probe_value)),
        ]
    )
    try:
        wrapped = raw_bytes(session.wrapKey(recovery, probe, PyKCS11.Mechanism(PyKCS11.CKM_AES_KEY_WRAP)))
    finally:
        session.destroyObject(probe)
    assert aes_key_unwrap(recovery_key, wrapped) == probe_value
    return wrapped


@pytest.fixture(scope="session", autouse=True)
def run_default_rotation():
    """Require the executable and commit the default dual-token rotation."""
    assert PROVISIONER.is_file(), "missing /app/bin/rotate_ceremony"
    assert os.access(PROVISIONER, os.X_OK), "/app/bin/rotate_ceremony is not executable"
    run(str(PROVISIONER))


def test_default_attestation_is_bound_to_both_live_tokens():
    """The attestation must derive from a decryptable envelope and both live signatures."""
    policy = json.loads(DEFAULT_POLICY_PATH.read_text())
    raw_output = DEFAULT_OUTPUT.read_bytes()
    assert raw_output.endswith(b"\n")
    attestation = json.loads(raw_output)
    assert set(attestation) == ATTESTATION_KEYS
    assert attestation["schema"] == "settlement-rotation-attestation-v2"
    assert attestation["primary_token_label"] == policy["primary_token"]["label"]
    assert attestation["escrow_token_label"] == policy["escrow_token"]["label"]
    assert attestation["epoch"] == policy["epoch"]
    for output_name, section, field in (
        ("retiring_key_id", "retiring", "id"),
        ("active_key_id", "active", "id"),
        ("recovery_key_id", "recovery", "id"),
        ("escrow_key_id", "escrow", "id"),
        ("envelope_object_id", "envelope", "object_id"),
        ("continuity_object_id", "continuity", "object_id"),
        ("receipt_object_id", "receipt", "object_id"),
    ):
        assert attestation[output_name] == policy[section][field]

    with token_session(policy) as primary:
        retiring_der = certificate_der(primary, policy["retiring"]["id"])
        active_der = certificate_der(primary, policy["active"]["id"])
        envelope = evidence_value(primary, policy, "envelope")
        continuity = evidence_value(primary, policy, "continuity")
        receipt = evidence_value(primary, policy, "receipt")
    with token_session(policy, "escrow") as escrow:
        escrow_der = certificate_der(escrow, policy["escrow"]["id"])

    recovery_key, _, aad = decode_envelope(policy, envelope, active_der)
    envelope_digest = hashlib.sha256(envelope).hexdigest()
    continuity_bytes = continuity_payload(policy, hashlib.sha256(active_der).hexdigest(), envelope_digest)
    receipt_bytes = receipt_payload(policy, hashlib.sha256(continuity).hexdigest(), envelope_digest)
    verify_pkcs1(retiring_der, continuity, continuity_bytes)
    verify_pkcs1(escrow_der, receipt, receipt_bytes)
    assert hashlib.sha256(aad).hexdigest() == json.loads(envelope)["aad_sha256"]
    assert attestation["retiring_certificate_sha256"] == hashlib.sha256(retiring_der).hexdigest()
    assert attestation["active_certificate_sha256"] == hashlib.sha256(active_der).hexdigest()
    assert attestation["escrow_certificate_sha256"] == hashlib.sha256(escrow_der).hexdigest()
    assert attestation["recovery_envelope_sha256"] == envelope_digest
    assert attestation["continuity_payload_sha256"] == hashlib.sha256(continuity_bytes).hexdigest()
    assert attestation["receipt_payload_sha256"] == hashlib.sha256(receipt_bytes).hexdigest()
    assert base64.b64decode(attestation["continuity_signature_base64"], validate=True) == continuity
    assert base64.b64decode(attestation["escrow_receipt_signature_base64"], validate=True) == receipt
    assert len(recovery_key) == 32
    assert not Path(policy["active"]["private_key_path"]).exists()


def test_committed_objects_enforce_cross_token_custody_boundaries():
    """Both tokens must expose only public evidence while enforcing exact key capabilities."""
    policy = json.loads(DEFAULT_POLICY_PATH.read_text())
    with token_session(policy, rw=True) as primary:
        assert not primary.findObjects([(PyKCS11.CKA_CLASS, PyKCS11.CKO_PRIVATE_KEY), (PyKCS11.CKA_ID, bytes.fromhex(policy["retiring"]["id"]))])
        active = find_one(primary, PyKCS11.CKO_PRIVATE_KEY, policy["active"]["id"])
        active_attrs = primary.getAttributeValue(
            active,
            [
                PyKCS11.CKA_KEY_TYPE,
                PyKCS11.CKA_TOKEN,
                PyKCS11.CKA_PRIVATE,
                PyKCS11.CKA_SENSITIVE,
                PyKCS11.CKA_EXTRACTABLE,
                PyKCS11.CKA_SIGN,
                PyKCS11.CKA_SIGN_RECOVER,
                PyKCS11.CKA_DECRYPT,
                PyKCS11.CKA_UNWRAP,
                PyKCS11.CKA_DERIVE,
                PyKCS11.CKA_ALLOWED_MECHANISMS,
            ],
        )
        assert active_attrs[:10] == [PyKCS11.CKK_RSA, True, True, True, False, True, False, False, False, False]
        assert allowed_mechanisms(active_attrs[10]) == (PyKCS11.CKM_SHA256_RSA_PKCS,)
        message = b"active-custody-verifier\n"
        signature = raw_bytes(primary.sign(active, message, PyKCS11.Mechanism(PyKCS11.CKM_SHA256_RSA_PKCS)))
        verify_pkcs1(certificate_der(primary, policy["active"]["id"]), signature, message)
        with pytest.raises(PyKCS11.PyKCS11Error):
            primary.sign(active, b"raw", PyKCS11.Mechanism(PyKCS11.CKM_RSA_PKCS))

        recovery = find_one(primary, PyKCS11.CKO_SECRET_KEY, policy["recovery"]["id"])
        recovery_attrs = primary.getAttributeValue(
            recovery,
            [
                PyKCS11.CKA_KEY_TYPE,
                PyKCS11.CKA_VALUE_LEN,
                PyKCS11.CKA_PRIVATE,
                PyKCS11.CKA_SENSITIVE,
                PyKCS11.CKA_EXTRACTABLE,
                PyKCS11.CKA_WRAP,
                PyKCS11.CKA_UNWRAP,
                PyKCS11.CKA_ENCRYPT,
                PyKCS11.CKA_DECRYPT,
                PyKCS11.CKA_SIGN,
                PyKCS11.CKA_VERIFY,
                PyKCS11.CKA_DERIVE,
                PyKCS11.CKA_ALLOWED_MECHANISMS,
            ],
        )
        assert recovery_attrs[:12] == [PyKCS11.CKK_AES, 32, True, True, False, True, False, False, False, False, False, False]
        assert allowed_mechanisms(recovery_attrs[12]) == (PyKCS11.CKM_AES_KEY_WRAP,)
        active_der = certificate_der(primary, policy["active"]["id"])
        envelope = evidence_value(primary, policy, "envelope")
        recovery_key, _, _ = decode_envelope(policy, envelope, active_der)
        wrap_probe(primary, policy, recovery_key, hashlib.sha256(envelope).hexdigest())

    with token_session(policy, "escrow") as escrow:
        escrow_private = find_one(escrow, PyKCS11.CKO_PRIVATE_KEY, policy["escrow"]["id"])
        escrow_attrs = escrow.getAttributeValue(
            escrow_private,
            [PyKCS11.CKA_KEY_TYPE, PyKCS11.CKA_TOKEN, PyKCS11.CKA_PRIVATE, PyKCS11.CKA_SENSITIVE, PyKCS11.CKA_EXTRACTABLE, PyKCS11.CKA_SIGN, PyKCS11.CKA_DECRYPT],
        )
        assert escrow_attrs == [PyKCS11.CKK_RSA, True, True, True, False, True, True]

    with token_session(policy, login=False) as primary_auditor:
        assert find_one(primary_auditor, PyKCS11.CKO_CERTIFICATE, policy["retiring"]["id"])
        assert find_one(primary_auditor, PyKCS11.CKO_CERTIFICATE, policy["active"]["id"])
        for name in ("envelope", "continuity", "receipt"):
            assert find_one(primary_auditor, PyKCS11.CKO_DATA, policy[name]["object_id"], object_id=True)
        assert not primary_auditor.findObjects([(PyKCS11.CKA_CLASS, PyKCS11.CKO_PRIVATE_KEY)])
        assert not primary_auditor.findObjects([(PyKCS11.CKA_CLASS, PyKCS11.CKO_SECRET_KEY)])
    with token_session(policy, "escrow", login=False) as escrow_auditor:
        assert find_one(escrow_auditor, PyKCS11.CKO_CERTIFICATE, policy["escrow"]["id"])
        assert not escrow_auditor.findObjects([(PyKCS11.CKA_CLASS, PyKCS11.CKO_PRIVATE_KEY)])


def test_rerun_preserves_envelope_evidence_recovery_and_unmanaged_objects():
    """A committed rerun must preserve both tokens and every generated security artifact."""
    policy = json.loads(DEFAULT_POLICY_PATH.read_text())
    with token_session(policy, rw=True) as primary:
        primary_anchor = find_one(primary, PyKCS11.CKO_CERTIFICATE, "ee01")
        primary_anchor_before = raw_bytes(primary.getAttributeValue(primary_anchor, [PyKCS11.CKA_VALUE])[0])
        evidence_before = {name: evidence_value(primary, policy, name) for name in ("envelope", "continuity", "receipt")}
        active_der = certificate_der(primary, policy["active"]["id"])
        recovery_key, _, _ = decode_envelope(policy, evidence_before["envelope"], active_der)
        wrapped_before = wrap_probe(primary, policy, recovery_key, hashlib.sha256(evidence_before["envelope"]).hexdigest())
    with token_session(policy, "escrow") as escrow:
        escrow_anchor = find_one(escrow, PyKCS11.CKO_CERTIFICATE, "ee02")
        escrow_anchor_before = raw_bytes(escrow.getAttributeValue(escrow_anchor, [PyKCS11.CKA_VALUE])[0])

    run(str(PROVISIONER))

    with token_session(policy, rw=True) as primary:
        primary_anchor = find_one(primary, PyKCS11.CKO_CERTIFICATE, "ee01")
        assert raw_bytes(primary.getAttributeValue(primary_anchor, [PyKCS11.CKA_VALUE])[0]) == primary_anchor_before
        for name, value in evidence_before.items():
            assert evidence_value(primary, policy, name) == value
        wrapped_after = wrap_probe(primary, policy, recovery_key, hashlib.sha256(evidence_before["envelope"]).hexdigest())
        assert wrapped_after == wrapped_before
        assert len(primary.findObjects([])) == 8
    with token_session(policy, "escrow") as escrow:
        escrow_anchor = find_one(escrow, PyKCS11.CKO_CERTIFICATE, "ee02")
        assert raw_bytes(escrow.getAttributeValue(escrow_anchor, [PyKCS11.CKA_VALUE])[0]) == escrow_anchor_before
        assert len(escrow.findObjects([])) == 3


def test_cli_rejects_invalid_forms_and_accepts_independent_overrides(tmp_path):
    """The documented CLI must reject malformed forms and honor both override orders."""
    policy = json.loads(DEFAULT_POLICY_PATH.read_text())
    for args in (
        ("--unknown",),
        ("--policy",),
        ("--output",),
        ("--policy", str(DEFAULT_POLICY_PATH), "--policy", str(DEFAULT_POLICY_PATH)),
        ("positional",),
    ):
        result = run(str(PROVISIONER), *args, check=False)
        assert result.returncode != 0
        assert result.stderr.startswith("rotate_ceremony:")
    duplicate_policy = tmp_path / "duplicate-policy.json"
    duplicate_policy.write_text(DEFAULT_POLICY_PATH.read_text().replace('  "epoch":', '  "epoch": "shadow",\n  "epoch":', 1))
    duplicate_output = tmp_path / "duplicate-output.json"
    duplicate_output.write_text("stale\n")
    result = run(str(PROVISIONER), "--policy", str(duplicate_policy), "--output", str(duplicate_output), check=False)
    assert result.returncode != 0
    assert result.stderr.startswith("rotate_ceremony:")
    assert not duplicate_output.exists()
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    run(str(PROVISIONER), "--output", str(first), "--policy", str(DEFAULT_POLICY_PATH))
    run(str(PROVISIONER), "--policy", str(DEFAULT_POLICY_PATH), "--output", str(second))
    assert json.loads(first.read_text())["primary_token_label"] == policy["primary_token"]["label"]
    assert first.read_bytes() == second.read_bytes()


def integer_bytes(value):
    return list(value.to_bytes((value.bit_length() + 7) // 8, "big"))


def private_template(key, identifier, label, *, decrypt=False, active=False):
    numbers = key.private_numbers()
    public = numbers.public_numbers
    template = [
        (PyKCS11.CKA_CLASS, PyKCS11.CKO_PRIVATE_KEY),
        (PyKCS11.CKA_KEY_TYPE, PyKCS11.CKK_RSA),
        (PyKCS11.CKA_TOKEN, True),
        (PyKCS11.CKA_PRIVATE, True),
        (PyKCS11.CKA_LABEL, label),
        (PyKCS11.CKA_ID, identifier),
        (PyKCS11.CKA_SENSITIVE, True),
        (PyKCS11.CKA_EXTRACTABLE, False),
        (PyKCS11.CKA_SIGN, True),
        (PyKCS11.CKA_SIGN_RECOVER, False),
        (PyKCS11.CKA_DECRYPT, decrypt),
        (PyKCS11.CKA_UNWRAP, False),
        (PyKCS11.CKA_DERIVE, False),
        (PyKCS11.CKA_MODULUS, integer_bytes(public.n)),
        (PyKCS11.CKA_PUBLIC_EXPONENT, integer_bytes(public.e)),
        (PyKCS11.CKA_PRIVATE_EXPONENT, integer_bytes(numbers.d)),
        (PyKCS11.CKA_PRIME_1, integer_bytes(numbers.p)),
        (PyKCS11.CKA_PRIME_2, integer_bytes(numbers.q)),
        (PyKCS11.CKA_EXPONENT_1, integer_bytes(numbers.dmp1)),
        (PyKCS11.CKA_EXPONENT_2, integer_bytes(numbers.dmq1)),
        (PyKCS11.CKA_COEFFICIENT, integer_bytes(numbers.iqmp)),
    ]
    if active:
        template.append((PyKCS11.CKA_ALLOWED_MECHANISMS, struct.pack("<Q", PyKCS11.CKM_SHA256_RSA_PKCS)))
    return template


def certificate_template(certificate, der, identifier, label):
    return [
        (PyKCS11.CKA_CLASS, PyKCS11.CKO_CERTIFICATE),
        (PyKCS11.CKA_CERTIFICATE_TYPE, PyKCS11.CKC_X_509),
        (PyKCS11.CKA_TOKEN, True),
        (PyKCS11.CKA_PRIVATE, False),
        (PyKCS11.CKA_LABEL, label),
        (PyKCS11.CKA_ID, identifier),
        (PyKCS11.CKA_SUBJECT, list(certificate.subject.public_bytes())),
        (PyKCS11.CKA_VALUE, list(der)),
    ]


def evidence_template(definition, value):
    return [
        (PyKCS11.CKA_CLASS, PyKCS11.CKO_DATA),
        (PyKCS11.CKA_TOKEN, True),
        (PyKCS11.CKA_PRIVATE, False),
        (PyKCS11.CKA_LABEL, definition["label"]),
        (PyKCS11.CKA_OBJECT_ID, bytes.fromhex(definition["object_id"])),
        (PyKCS11.CKA_APPLICATION, definition["application"]),
        (PyKCS11.CKA_VALUE, list(value)),
    ]


def recovery_template(policy, value):
    return [
        (PyKCS11.CKA_CLASS, PyKCS11.CKO_SECRET_KEY),
        (PyKCS11.CKA_KEY_TYPE, PyKCS11.CKK_AES),
        (PyKCS11.CKA_TOKEN, True),
        (PyKCS11.CKA_PRIVATE, True),
        (PyKCS11.CKA_LABEL, policy["recovery"]["label"]),
        (PyKCS11.CKA_ID, bytes.fromhex(policy["recovery"]["id"])),
        (PyKCS11.CKA_VALUE, list(value)),
        (PyKCS11.CKA_SENSITIVE, True),
        (PyKCS11.CKA_EXTRACTABLE, False),
        (PyKCS11.CKA_WRAP, True),
        (PyKCS11.CKA_UNWRAP, False),
        (PyKCS11.CKA_ENCRYPT, False),
        (PyKCS11.CKA_DECRYPT, False),
        (PyKCS11.CKA_SIGN, False),
        (PyKCS11.CKA_VERIFY, False),
        (PyKCS11.CKA_DERIVE, False),
        (PyKCS11.CKA_ALLOWED_MECHANISMS, struct.pack("<Q", PyKCS11.CKM_AES_KEY_WRAP)),
    ]


def make_pair(common_name, bits=2048):
    key = rsa.generate_private_key(public_exponent=65537, key_size=bits)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=30))
        .sign(key, hashes.SHA256())
    )
    return key, certificate, certificate.public_bytes(serialization.Encoding.DER)


def distinct_ids(count):
    while True:
        values = [secrets.token_hex(3) for _ in range(count)]
        if len(set(values)) == len(values):
            return values


def initialize_token(label, user_pin, so_pin):
    library = pkcs11_library()
    free_slots = []
    for slot in library.getSlotList(tokenPresent=True):
        info = library.getTokenInfo(slot)
        if not (info.flags & PyKCS11.CKF_TOKEN_INITIALIZED):
            free_slots.append(slot)
    assert free_slots, "SoftHSM has no uninitialized slot"
    slot = free_slots[0]
    library.initToken(slot, so_pin, label.ljust(32))
    reload_pkcs11_library()
    library = pkcs11_library()
    slot = token_slot(library, label)
    session = library.openSession(slot, PyKCS11.CKF_SERIAL_SESSION | PyKCS11.CKF_RW_SESSION)
    try:
        session.login(so_pin, PyKCS11.CKU_SO)
        session.initPin(user_pin)
        session.logout()
    finally:
        session.closeSession()
    reload_pkcs11_library()


def build_case_evidence(policy, active_key, active_der, escrow_certificate, retiring_key, escrow_key):
    recovery_key = secrets.token_bytes(32)
    nonce = secrets.token_bytes(12)
    aad = envelope_aad(policy, hashlib.sha256(active_der).hexdigest())
    private_der = active_key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    encrypted = AESGCM(recovery_key).encrypt(nonce, private_der, aad)
    wrapped = escrow_certificate.public_key().encrypt(
        recovery_key,
        padding.OAEP(mgf=padding.MGF1(hashes.SHA1()), algorithm=hashes.SHA1(), label=None),
    )
    envelope = canonical_envelope(
        {
            "schema": "settlement-recovery-envelope-v2",
            "aad_sha256": hashlib.sha256(aad).hexdigest(),
            "nonce_base64": base64.b64encode(nonce).decode(),
            "wrapped_recovery_key_base64": base64.b64encode(wrapped).decode(),
            "encrypted_private_key_base64": base64.b64encode(encrypted).decode(),
        }
    )
    envelope_digest = hashlib.sha256(envelope).hexdigest()
    continuity_bytes = continuity_payload(policy, hashlib.sha256(active_der).hexdigest(), envelope_digest)
    continuity = retiring_key.sign(continuity_bytes, padding.PKCS1v15(), hashes.SHA256())
    receipt_bytes = receipt_payload(policy, hashlib.sha256(continuity).hexdigest(), envelope_digest)
    receipt = escrow_key.sign(receipt_bytes, padding.PKCS1v15(), hashes.SHA256())
    return {
        "recovery_key": recovery_key,
        "envelope": envelope,
        "continuity": continuity,
        "receipt": receipt,
    }


def create_case(tmp_path, mode="initial"):
    tmp_path.mkdir(parents=True, exist_ok=True)
    suffix = secrets.token_hex(4)
    primary_label = f"PRIMARY-{suffix}"
    escrow_label = f"ESCROW-{suffix}"
    primary_pin = f"Primary-{suffix}-284"
    escrow_pin = f"Escrow-{suffix}-593"
    ids = distinct_ids(9)
    retiring_id, active_id, recovery_id, escrow_id, envelope_id, continuity_id, receipt_id, unmanaged_primary_id, unmanaged_escrow_id = ids
    retiring_key, retiring_certificate, retiring_der = make_pair(f"retiring-{suffix}")
    active_key, active_certificate, active_der = make_pair(f"active-{suffix}", bits=3072)
    escrow_key, escrow_certificate, escrow_der = make_pair(f"escrow-{suffix}", bits=3072)
    key_path = tmp_path / f"incoming-{suffix}.pem"
    cert_path = tmp_path / f"incoming-{suffix}.crt"
    policy_path = tmp_path / f"policy-{suffix}.json"
    output_path = tmp_path / f"attestation-{suffix}.json"
    key_path.write_bytes(active_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    cert_path.write_bytes(active_certificate.public_bytes(serialization.Encoding.PEM))
    policy = {
        "schema": "settlement-key-rotation-v2",
        "primary_token": {"label": primary_label, "user_pin": primary_pin},
        "escrow_token": {"label": escrow_label, "user_pin": escrow_pin},
        "epoch": f"epoch-{suffix}",
        "retiring": {"id": retiring_id, "private_label": f"retiring-key-{suffix}", "certificate_label": f"retiring-cert-{suffix}"},
        "active": {
            "id": active_id,
            "private_label": f"active-key-{suffix}",
            "certificate_label": f"active-cert-{suffix}",
            "private_key_path": str(key_path),
            "certificate_path": str(cert_path),
            "allowed_mechanism": "SHA256-RSA-PKCS",
        },
        "recovery": {"id": recovery_id, "label": f"recovery-{suffix}", "bytes": 32, "allowed_mechanism": "AES-KEY-WRAP"},
        "escrow": {
            "id": escrow_id,
            "private_label": f"escrow-key-{suffix}",
            "certificate_label": f"escrow-cert-{suffix}",
            "key_wrap_mechanism": "RSA-PKCS-OAEP-SHA1",
        },
        "envelope": {"object_id": envelope_id, "label": f"envelope-{suffix}", "application": "settlement-recovery-envelope-v2", "cipher": "AES-256-GCM"},
        "continuity": {"object_id": continuity_id, "label": f"continuity-{suffix}", "application": "settlement-rotation-continuity-v2"},
        "receipt": {"object_id": receipt_id, "label": f"receipt-{suffix}", "application": "settlement-escrow-receipt-v2"},
    }
    policy_path.write_text(json.dumps(policy, indent=2) + "\n")
    initialize_token(primary_label, primary_pin, f"Primary-SO-{suffix}")
    initialize_token(escrow_label, escrow_pin, f"Escrow-SO-{suffix}")
    unmanaged_primary = f"primary-unmanaged-{suffix}".encode()
    unmanaged_escrow = f"escrow-unmanaged-{suffix}".encode()
    with token_session(policy, rw=True) as primary:
        primary.createObject(certificate_template(retiring_certificate, retiring_der, bytes.fromhex(retiring_id), policy["retiring"]["certificate_label"]))
        primary.createObject(private_template(retiring_key, bytes.fromhex(retiring_id), policy["retiring"]["private_label"]))
        primary.createObject(
            [
                (PyKCS11.CKA_CLASS, PyKCS11.CKO_DATA),
                (PyKCS11.CKA_TOKEN, True),
                (PyKCS11.CKA_PRIVATE, False),
                (PyKCS11.CKA_LABEL, f"unmanaged-primary-{suffix}"),
                (PyKCS11.CKA_APPLICATION, "independent-primary-state"),
                (PyKCS11.CKA_OBJECT_ID, bytes.fromhex(unmanaged_primary_id)),
                (PyKCS11.CKA_VALUE, list(unmanaged_primary)),
            ]
        )
    with token_session(policy, "escrow", rw=True) as escrow:
        escrow.createObject(certificate_template(escrow_certificate, escrow_der, bytes.fromhex(escrow_id), policy["escrow"]["certificate_label"]))
        escrow.createObject(private_template(escrow_key, bytes.fromhex(escrow_id), policy["escrow"]["private_label"], decrypt=True))
        escrow.createObject(
            [
                (PyKCS11.CKA_CLASS, PyKCS11.CKO_DATA),
                (PyKCS11.CKA_TOKEN, True),
                (PyKCS11.CKA_PRIVATE, False),
                (PyKCS11.CKA_LABEL, f"unmanaged-escrow-{suffix}"),
                (PyKCS11.CKA_APPLICATION, "independent-escrow-state"),
                (PyKCS11.CKA_OBJECT_ID, bytes.fromhex(unmanaged_escrow_id)),
                (PyKCS11.CKA_VALUE, list(unmanaged_escrow)),
            ]
        )

    evidence = build_case_evidence(policy, active_key, active_der, escrow_certificate, retiring_key, escrow_key)
    with token_session(policy, rw=True) as primary:
        if mode not in {"initial", "mismatched_stage", "label_collision"}:
            envelope_value = evidence["envelope"]
            if mode == "corrupt_envelope":
                parsed = json.loads(envelope_value)
                encrypted = bytearray(base64.b64decode(parsed["encrypted_private_key_base64"]))
                encrypted[-1] ^= 1
                parsed["encrypted_private_key_base64"] = base64.b64encode(encrypted).decode()
                envelope_value = canonical_envelope(parsed)
            primary.createObject(evidence_template(policy["envelope"], envelope_value))
        if mode in {"evidence", "custody_partial", "committed", "corrupt_receipt", "recovery_mismatch", "duplicate"}:
            primary.createObject(evidence_template(policy["continuity"], evidence["continuity"]))
            receipt_value = secrets.token_bytes(len(evidence["receipt"])) if mode == "corrupt_receipt" else evidence["receipt"]
            primary.createObject(evidence_template(policy["receipt"], receipt_value))
        if mode in {"custody_partial", "committed"}:
            primary.createObject(certificate_template(active_certificate, active_der, bytes.fromhex(active_id), policy["active"]["certificate_label"]))
            primary.createObject(private_template(active_key, bytes.fromhex(active_id), policy["active"]["private_label"], active=True))
        if mode == "committed":
            primary.createObject(recovery_template(policy, evidence["recovery_key"]))
            primary.destroyObject(find_one(primary, PyKCS11.CKO_PRIVATE_KEY, retiring_id))
        if mode == "recovery_mismatch":
            primary.createObject(recovery_template(policy, secrets.token_bytes(32)))
        if mode == "irrecoverable":
            primary.destroyObject(find_one(primary, PyKCS11.CKO_PRIVATE_KEY, retiring_id))
        if mode == "duplicate":
            primary.createObject(evidence_template(policy["envelope"], evidence["envelope"]))
        if mode == "label_collision":
            primary.createObject(
                [
                    (PyKCS11.CKA_CLASS, PyKCS11.CKO_DATA),
                    (PyKCS11.CKA_TOKEN, True),
                    (PyKCS11.CKA_PRIVATE, False),
                    (PyKCS11.CKA_LABEL, policy["envelope"]["label"]),
                    (PyKCS11.CKA_APPLICATION, "conflicting-unmanaged-state"),
                    (PyKCS11.CKA_OBJECT_ID, bytes.fromhex(unmanaged_escrow_id)),
                    (PyKCS11.CKA_VALUE, list(b"collision")),
                ]
            )

    if mode == "mismatched_stage":
        wrong_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        key_path.write_bytes(wrong_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    if mode in {"sealed", "evidence", "custody_partial", "committed", "corrupt_envelope", "corrupt_receipt", "recovery_mismatch", "irrecoverable", "duplicate"}:
        key_path.unlink()
    return {
        "policy": policy,
        "policy_path": policy_path,
        "output_path": output_path,
        "key_path": key_path,
        "active_der": active_der,
        "escrow_der": escrow_der,
        "evidence": evidence,
        "unmanaged_primary": unmanaged_primary,
        "unmanaged_escrow": unmanaged_escrow,
        "unmanaged_primary_id": unmanaged_primary_id,
        "unmanaged_escrow_id": unmanaged_escrow_id,
    }


def snapshot_token(policy, token_kind):
    rows = []
    with token_session(policy, token_kind) as session:
        for handle in session.findObjects([]):
            values = []
            for attribute in (
                PyKCS11.CKA_CLASS,
                PyKCS11.CKA_KEY_TYPE,
                PyKCS11.CKA_LABEL,
                PyKCS11.CKA_ID,
                PyKCS11.CKA_OBJECT_ID,
                PyKCS11.CKA_APPLICATION,
                PyKCS11.CKA_PRIVATE,
                PyKCS11.CKA_SENSITIVE,
                PyKCS11.CKA_EXTRACTABLE,
                PyKCS11.CKA_SIGN,
                PyKCS11.CKA_DECRYPT,
                PyKCS11.CKA_WRAP,
                PyKCS11.CKA_ALLOWED_MECHANISMS,
                PyKCS11.CKA_VALUE,
            ):
                try:
                    value = session.getAttributeValue(handle, [attribute])[0]
                except PyKCS11.PyKCS11Error:
                    value = None
                if isinstance(value, (list, tuple, bytearray, bytes)):
                    value = bytes(value).hex()
                values.append(value)
            rows.append(tuple(values))
    return sorted(rows, key=repr)


def assert_case_final(case):
    policy = case["policy"]
    attestation = json.loads(case["output_path"].read_text())
    assert set(attestation) == ATTESTATION_KEYS
    with token_session(policy, rw=True) as primary:
        assert not primary.findObjects([(PyKCS11.CKA_CLASS, PyKCS11.CKO_PRIVATE_KEY), (PyKCS11.CKA_ID, bytes.fromhex(policy["retiring"]["id"]))])
        active_der = certificate_der(primary, policy["active"]["id"])
        envelope = evidence_value(primary, policy, "envelope")
        continuity = evidence_value(primary, policy, "continuity")
        receipt = evidence_value(primary, policy, "receipt")
        recovery_key, _, _ = decode_envelope(policy, envelope, active_der)
        wrap_probe(primary, policy, recovery_key, hashlib.sha256(envelope).hexdigest())
        unmanaged = find_one(primary, PyKCS11.CKO_DATA, case["unmanaged_primary_id"], object_id=True)
        assert raw_bytes(primary.getAttributeValue(unmanaged, [PyKCS11.CKA_VALUE])[0]) == case["unmanaged_primary"]
    with token_session(policy, "escrow") as escrow:
        unmanaged = find_one(escrow, PyKCS11.CKO_DATA, case["unmanaged_escrow_id"], object_id=True)
        assert raw_bytes(escrow.getAttributeValue(unmanaged, [PyKCS11.CKA_VALUE])[0]) == case["unmanaged_escrow"]
        escrow_der = certificate_der(escrow, policy["escrow"]["id"])
    envelope_digest = hashlib.sha256(envelope).hexdigest()
    verify_pkcs1(certificate_der_from_case(case, "retiring"), continuity, continuity_payload(policy, hashlib.sha256(active_der).hexdigest(), envelope_digest))
    verify_pkcs1(escrow_der, receipt, receipt_payload(policy, hashlib.sha256(continuity).hexdigest(), envelope_digest))
    assert not case["key_path"].exists()
    if case["evidence"]["envelope"] == envelope:
        assert envelope == case["evidence"]["envelope"]
    return envelope, continuity, receipt


def certificate_der_from_case(case, which):
    policy = case["policy"]
    with token_session(policy) as primary:
        return certificate_der(primary, policy[which]["id"])


@pytest.mark.parametrize("mode", ["sealed", "custody_partial", "committed"])
def test_randomized_dual_token_cut_points_resume_without_staged_key(tmp_path, mode):
    """Randomized envelope-only, custody-partial, and committed cuts must converge exactly."""
    case = create_case(tmp_path, mode=mode)
    before = {name: case["evidence"][name] for name in ("envelope", "continuity", "receipt") if mode != "sealed" or name == "envelope"}
    run(str(PROVISIONER), "--output", str(case["output_path"]), "--policy", str(case["policy_path"]))
    envelope, continuity, receipt = assert_case_final(case)
    actual = {"envelope": envelope, "continuity": continuity, "receipt": receipt}
    for name, value in before.items():
        assert actual[name] == value


def assert_preflight_failure(case):
    case["output_path"].write_text("stale\n")
    primary_before = snapshot_token(case["policy"], "primary")
    escrow_before = snapshot_token(case["policy"], "escrow")
    key_before = case["key_path"].read_bytes() if case["key_path"].exists() else None
    result = run(str(PROVISIONER), "--policy", str(case["policy_path"]), "--output", str(case["output_path"]), check=False)
    assert result.returncode != 0
    assert result.stderr.startswith("rotate_ceremony:")
    assert not case["output_path"].exists()
    assert snapshot_token(case["policy"], "primary") == primary_before
    assert snapshot_token(case["policy"], "escrow") == escrow_before
    if key_before is not None:
        assert case["key_path"].read_bytes() == key_before


def test_mismatched_staged_key_fails_before_either_token_changes(tmp_path):
    """A staged key that conflicts with the certificate must fail before persistent mutation."""
    assert_preflight_failure(create_case(tmp_path, mode="mismatched_stage"))


def test_corrupt_envelope_fails_without_replacing_durable_bytes(tmp_path):
    """An AES-GCM-invalid durable envelope must never be repaired or replaced."""
    assert_preflight_failure(create_case(tmp_path, mode="corrupt_envelope"))


def test_invalid_escrow_receipt_fails_without_using_a_new_signature(tmp_path):
    """A bad existing countersignature must fail closed even though the escrow key is usable."""
    assert_preflight_failure(create_case(tmp_path, mode="corrupt_receipt"))


def test_envelope_recovery_key_mismatch_is_rejected_before_mutation(tmp_path):
    """A correctly shaped recovery object bound to different bytes must be detected by wrapping."""
    assert_preflight_failure(create_case(tmp_path, mode="recovery_mismatch"))


def test_irrecoverable_and_duplicate_evidence_states_fail_closed(tmp_path):
    """Missing continuity, duplicate evidence, and a managed-label collision must all fail closed."""
    assert_preflight_failure(create_case(tmp_path / "irrecoverable", mode="irrecoverable"))
    assert_preflight_failure(create_case(tmp_path / "duplicate", mode="duplicate"))
    assert_preflight_failure(create_case(tmp_path / "label-collision", mode="label_collision"))
