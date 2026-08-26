#!/usr/bin/env python3
import base64
import binascii
import hashlib
import json
import re
import secrets
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

import PyKCS11
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.keywrap import aes_key_unwrap

MODULE = "/usr/lib/softhsm/libsofthsm2.so"
HEX_ID = re.compile(r"(?:[0-9a-f]{2}){1,32}\Z")


class CeremonyError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise CeremonyError(message)


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise CeremonyError(f"policy contains duplicate JSON member {key!r}")
        value[key] = item
    return value


def read_json(path):
    try:
        with open(path, encoding="utf-8") as handle:
            value = json.load(handle, object_pairs_hook=unique_object)
    except CeremonyError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CeremonyError(f"cannot read policy: {exc}") from exc
    require(isinstance(value, dict), "policy must be a JSON object")
    return value


def exact_keys(value, expected, description):
    require(isinstance(value, dict), f"{description} must be a JSON object")
    require(set(value) == set(expected), f"{description} has missing or additional members")


def validate_string(value, description):
    require(isinstance(value, str) and value != "", f"{description} must be a nonempty string")
    require("\r" not in value and "\n" not in value, f"{description} contains a line break")


def validate_policy(policy):
    exact_keys(
        policy,
        [
            "schema",
            "primary_token",
            "escrow_token",
            "epoch",
            "retiring",
            "active",
            "recovery",
            "escrow",
            "envelope",
            "continuity",
            "receipt",
        ],
        "policy",
    )
    exact_keys(policy["primary_token"], ["label", "user_pin"], "primary_token")
    exact_keys(policy["escrow_token"], ["label", "user_pin"], "escrow_token")
    exact_keys(policy["retiring"], ["id", "private_label", "certificate_label"], "retiring")
    exact_keys(
        policy["active"],
        ["id", "private_label", "certificate_label", "private_key_path", "certificate_path", "allowed_mechanism"],
        "active",
    )
    exact_keys(policy["recovery"], ["id", "label", "bytes", "allowed_mechanism"], "recovery")
    exact_keys(policy["escrow"], ["id", "private_label", "certificate_label", "key_wrap_mechanism"], "escrow")
    exact_keys(policy["envelope"], ["object_id", "label", "application", "cipher"], "envelope")
    exact_keys(policy["continuity"], ["object_id", "label", "application"], "continuity")
    exact_keys(policy["receipt"], ["object_id", "label", "application"], "receipt")

    strings = [
        ("schema", policy["schema"]),
        ("primary_token.label", policy["primary_token"]["label"]),
        ("primary_token.user_pin", policy["primary_token"]["user_pin"]),
        ("escrow_token.label", policy["escrow_token"]["label"]),
        ("escrow_token.user_pin", policy["escrow_token"]["user_pin"]),
        ("epoch", policy["epoch"]),
    ]
    for section in ("retiring", "active", "recovery", "escrow", "envelope", "continuity", "receipt"):
        for key, value in policy[section].items():
            if key != "bytes":
                strings.append((f"{section}.{key}", value))
    for name, value in strings:
        validate_string(value, name)

    require(policy["schema"] == "settlement-key-rotation-v2", "unsupported policy schema")
    require(policy["primary_token"]["label"] != policy["escrow_token"]["label"], "token labels must differ")
    ids = [
        policy["retiring"]["id"],
        policy["active"]["id"],
        policy["recovery"]["id"],
        policy["escrow"]["id"],
        policy["envelope"]["object_id"],
        policy["continuity"]["object_id"],
        policy["receipt"]["object_id"],
    ]
    require(all(HEX_ID.fullmatch(value) for value in ids), "policy identifiers must be lowercase even-length hexadecimal")
    require(len(set(ids)) == len(ids), "policy identifiers must be distinct")
    labels = [
        policy["retiring"]["private_label"],
        policy["retiring"]["certificate_label"],
        policy["active"]["private_label"],
        policy["active"]["certificate_label"],
        policy["recovery"]["label"],
        policy["escrow"]["private_label"],
        policy["escrow"]["certificate_label"],
        policy["envelope"]["label"],
        policy["continuity"]["label"],
        policy["receipt"]["label"],
    ]
    require(len(set(labels)) == len(labels), "managed object labels must be distinct")
    require(policy["active"]["allowed_mechanism"] == "SHA256-RSA-PKCS", "unsupported active mechanism")
    require(policy["recovery"]["bytes"] == 32, "recovery key must be 32 bytes")
    require(policy["recovery"]["allowed_mechanism"] == "AES-KEY-WRAP", "unsupported recovery mechanism")
    require(policy["escrow"]["key_wrap_mechanism"] == "RSA-PKCS-OAEP-SHA1", "unsupported escrow mechanism")
    require(policy["envelope"]["application"] == "settlement-recovery-envelope-v2", "unsupported envelope application")
    require(policy["envelope"]["cipher"] == "AES-256-GCM", "unsupported envelope cipher")
    require(policy["continuity"]["application"] == "settlement-rotation-continuity-v2", "unsupported continuity application")
    require(policy["receipt"]["application"] == "settlement-escrow-receipt-v2", "unsupported receipt application")
    for field in ("private_key_path", "certificate_path"):
        require(Path(policy["active"][field]).is_absolute(), f"active.{field} must be absolute")


def load_certificate(path, description):
    try:
        certificate = x509.load_pem_x509_certificate(Path(path).read_bytes())
    except (OSError, ValueError) as exc:
        raise CeremonyError(f"cannot read {description}: {exc}") from exc
    public_key = certificate.public_key()
    require(isinstance(public_key, rsa.RSAPublicKey), f"{description} must contain an RSA public key")
    require(public_key.key_size >= 2048, f"{description} RSA key is too small")
    return certificate, certificate.public_bytes(serialization.Encoding.DER)


def load_optional_private_key(path, certificate):
    if not Path(path).exists():
        return None
    try:
        key = serialization.load_pem_private_key(Path(path).read_bytes(), password=None)
    except (OSError, ValueError, TypeError) as exc:
        raise CeremonyError(f"cannot read incoming private key: {exc}") from exc
    require(isinstance(key, rsa.RSAPrivateKey), "incoming private key must be RSA")
    require(key.key_size >= 2048, "incoming private RSA key is too small")
    require(key.public_key().public_numbers() == certificate.public_key().public_numbers(), "incoming key does not match incoming certificate")
    return key


def as_bytes(value):
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, str):
        return value.encode()
    return bytes(value)


def safe_attribute(session, handle, attribute):
    try:
        return session.getAttributeValue(handle, [attribute])[0]
    except PyKCS11.PyKCS11Error:
        return None


def safe_bytes(session, handle, attribute):
    value = safe_attribute(session, handle, attribute)
    if value is None:
        return b""
    try:
        return as_bytes(value)
    except (TypeError, ValueError):
        return b""


def token_slot(library, label):
    slots = [slot for slot in library.getSlotList(tokenPresent=True) if library.getTokenInfo(slot).label.strip() == label]
    require(len(slots) == 1, f"exactly one token named {label!r} must exist")
    return slots[0]


def open_logged_session(library, token):
    slot = token_slot(library, token["label"])
    session = library.openSession(slot, PyKCS11.CKF_SERIAL_SESSION | PyKCS11.CKF_RW_SESSION)
    try:
        session.login(token["user_pin"])
    except PyKCS11.PyKCS11Error as exc:
        session.closeSession()
        raise CeremonyError(f"cannot authenticate to token {token['label']!r}") from exc
    return slot, session


def managed_ids(policy):
    return {
        bytes.fromhex(policy["retiring"]["id"]),
        bytes.fromhex(policy["active"]["id"]),
        bytes.fromhex(policy["recovery"]["id"]),
        bytes.fromhex(policy["escrow"]["id"]),
        bytes.fromhex(policy["envelope"]["object_id"]),
        bytes.fromhex(policy["continuity"]["object_id"]),
        bytes.fromhex(policy["receipt"]["object_id"]),
    }


def managed_labels(policy):
    return {
        policy["retiring"]["private_label"],
        policy["retiring"]["certificate_label"],
        policy["active"]["private_label"],
        policy["active"]["certificate_label"],
        policy["recovery"]["label"],
        policy["escrow"]["private_label"],
        policy["escrow"]["certificate_label"],
        policy["envelope"]["label"],
        policy["continuity"]["label"],
        policy["receipt"]["label"],
    }


def inventory(session, policy, token_kind):
    definitions = {}
    if token_kind == "primary":
        definitions = {
            "retiring_certificate": (PyKCS11.CKO_CERTIFICATE, bytes.fromhex(policy["retiring"]["id"]), False, policy["retiring"]["certificate_label"]),
            "retiring_private": (PyKCS11.CKO_PRIVATE_KEY, bytes.fromhex(policy["retiring"]["id"]), False, policy["retiring"]["private_label"]),
            "active_certificate": (PyKCS11.CKO_CERTIFICATE, bytes.fromhex(policy["active"]["id"]), False, policy["active"]["certificate_label"]),
            "active_private": (PyKCS11.CKO_PRIVATE_KEY, bytes.fromhex(policy["active"]["id"]), False, policy["active"]["private_label"]),
            "recovery": (PyKCS11.CKO_SECRET_KEY, bytes.fromhex(policy["recovery"]["id"]), False, policy["recovery"]["label"]),
            "envelope": (PyKCS11.CKO_DATA, bytes.fromhex(policy["envelope"]["object_id"]), True, policy["envelope"]["label"]),
            "continuity": (PyKCS11.CKO_DATA, bytes.fromhex(policy["continuity"]["object_id"]), True, policy["continuity"]["label"]),
            "receipt": (PyKCS11.CKO_DATA, bytes.fromhex(policy["receipt"]["object_id"]), True, policy["receipt"]["label"]),
        }
    else:
        definitions = {
            "escrow_certificate": (PyKCS11.CKO_CERTIFICATE, bytes.fromhex(policy["escrow"]["id"]), False, policy["escrow"]["certificate_label"]),
            "escrow_private": (PyKCS11.CKO_PRIVATE_KEY, bytes.fromhex(policy["escrow"]["id"]), False, policy["escrow"]["private_label"]),
        }
    found = {name: [] for name in definitions}
    ids = managed_ids(policy)
    labels = managed_labels(policy)
    for handle in session.findObjects([]):
        object_class = safe_attribute(session, handle, PyKCS11.CKA_CLASS)
        identifier = safe_bytes(session, handle, PyKCS11.CKA_ID)
        object_id = safe_bytes(session, handle, PyKCS11.CKA_OBJECT_ID)
        label = safe_attribute(session, handle, PyKCS11.CKA_LABEL)
        matched = None
        for name, (expected_class, expected_identifier, use_object_id, expected_label) in definitions.items():
            actual_identifier = object_id if use_object_id else identifier
            if object_class == expected_class and actual_identifier == expected_identifier and label == expected_label:
                matched = name
                break
        touches_managed = identifier in ids or object_id in ids or label in labels
        if matched is not None:
            found[matched].append(handle)
        elif touches_managed:
            raise CeremonyError(f"conflicting managed object in {token_kind} token")
    for name, handles in found.items():
        require(len(handles) <= 1, f"ambiguous managed state: duplicate {name.replace('_', ' ')}")
    return {name: handles[0] if handles else None for name, handles in found.items()}


def certificate_bytes(session, handle, identifier, label, description):
    attrs = session.getAttributeValue(
        handle,
        [PyKCS11.CKA_CLASS, PyKCS11.CKA_TOKEN, PyKCS11.CKA_PRIVATE, PyKCS11.CKA_LABEL, PyKCS11.CKA_ID, PyKCS11.CKA_CERTIFICATE_TYPE, PyKCS11.CKA_VALUE],
    )
    require(attrs[0] == PyKCS11.CKO_CERTIFICATE and attrs[1] is True and attrs[2] is False, f"invalid {description} attributes")
    require(attrs[3] == label and as_bytes(attrs[4]) == identifier and attrs[5] == PyKCS11.CKC_X_509, f"invalid {description} identity")
    der = as_bytes(attrs[6])
    try:
        certificate = x509.load_der_x509_certificate(der)
    except ValueError as exc:
        raise CeremonyError(f"{description} is not a valid X.509 certificate") from exc
    public_key = certificate.public_key()
    require(isinstance(public_key, rsa.RSAPublicKey) and public_key.key_size >= 2048, f"{description} must contain an RSA key of at least 2048 bits")
    return certificate, der


def verify_signature(certificate, signature, payload, description):
    try:
        certificate.public_key().verify(signature, payload, padding.PKCS1v15(), hashes.SHA256())
    except InvalidSignature as exc:
        raise CeremonyError(f"{description} does not verify") from exc


def mechanism_values(value):
    raw = as_bytes(value)
    require(len(raw) > 0 and len(raw) % 8 == 0, "invalid CKA_ALLOWED_MECHANISMS encoding")
    return tuple(struct.unpack("<Q", raw[offset : offset + 8])[0] for offset in range(0, len(raw), 8))


def validate_retiring_private(session, handle, policy, certificate):
    attrs = session.getAttributeValue(
        handle,
        [PyKCS11.CKA_CLASS, PyKCS11.CKA_KEY_TYPE, PyKCS11.CKA_TOKEN, PyKCS11.CKA_PRIVATE, PyKCS11.CKA_SENSITIVE, PyKCS11.CKA_EXTRACTABLE, PyKCS11.CKA_SIGN],
    )
    require(attrs == [PyKCS11.CKO_PRIVATE_KEY, PyKCS11.CKK_RSA, True, True, True, False, True], "retiring private key attributes violate policy")
    probe = b"retiring-key-binding-v2\n"
    try:
        signature = as_bytes(session.sign(handle, probe, PyKCS11.Mechanism(PyKCS11.CKM_SHA256_RSA_PKCS)))
    except PyKCS11.PyKCS11Error as exc:
        raise CeremonyError("retiring private key cannot sign") from exc
    verify_signature(certificate, signature, probe, "retiring private key certificate binding")


def validate_escrow_private(session, handle, certificate):
    attrs = session.getAttributeValue(
        handle,
        [PyKCS11.CKA_CLASS, PyKCS11.CKA_KEY_TYPE, PyKCS11.CKA_TOKEN, PyKCS11.CKA_PRIVATE, PyKCS11.CKA_SENSITIVE, PyKCS11.CKA_EXTRACTABLE, PyKCS11.CKA_SIGN, PyKCS11.CKA_DECRYPT],
    )
    require(attrs == [PyKCS11.CKO_PRIVATE_KEY, PyKCS11.CKK_RSA, True, True, True, False, True, True], "escrow private key attributes violate policy")
    probe = b"escrow-key-binding-v2\n"
    try:
        signature = as_bytes(session.sign(handle, probe, PyKCS11.Mechanism(PyKCS11.CKM_SHA256_RSA_PKCS)))
    except PyKCS11.PyKCS11Error as exc:
        raise CeremonyError("escrow private key cannot sign") from exc
    verify_signature(certificate, signature, probe, "escrow private key certificate binding")


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
    ).encode("utf-8")


def strict_b64(value, description):
    require(isinstance(value, str), f"{description} must be base64 text")
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise CeremonyError(f"invalid {description}") from exc
    require(base64.b64encode(raw).decode("ascii") == value, f"noncanonical {description}")
    return raw


def canonical_envelope(value):
    return (json.dumps(value, ensure_ascii=True, separators=(",", ":")) + "\n").encode("utf-8")


def decrypt_oaep(policy, wrapped):
    with tempfile.TemporaryDirectory(prefix="rotate-escrow-") as directory:
        wrapped_path = Path(directory) / "wrapped.bin"
        clear_path = Path(directory) / "clear.bin"
        wrapped_path.write_bytes(wrapped)
        result = subprocess.run(
            [
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
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode != 0 or not clear_path.is_file():
            raise CeremonyError("escrow private key cannot decrypt recovery envelope")
        clear = clear_path.read_bytes()
        clear_path.write_bytes(b"\0" * len(clear))
        return clear


def build_envelope(policy, escrow_certificate, active_der, active_key):
    recovery_key = secrets.token_bytes(32)
    nonce = secrets.token_bytes(12)
    aad = envelope_aad(policy, hashlib.sha256(active_der).hexdigest())
    private_der = active_key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    encrypted = AESGCM(recovery_key).encrypt(nonce, private_der, aad)
    wrapped = escrow_certificate.public_key().encrypt(
        recovery_key,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA1()), algorithm=hashes.SHA1(), label=None),
    )
    value = {
        "schema": "settlement-recovery-envelope-v2",
        "aad_sha256": hashlib.sha256(aad).hexdigest(),
        "nonce_base64": base64.b64encode(nonce).decode("ascii"),
        "wrapped_recovery_key_base64": base64.b64encode(wrapped).decode("ascii"),
        "encrypted_private_key_base64": base64.b64encode(encrypted).decode("ascii"),
    }
    return canonical_envelope(value)


def decode_envelope(policy, envelope_bytes, escrow_certificate, active_certificate, active_der, staged_key):
    try:
        value = json.loads(envelope_bytes.decode("utf-8"), object_pairs_hook=unique_object)
    except CeremonyError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CeremonyError("recovery envelope is not valid JSON") from exc
    exact_keys(value, ["schema", "aad_sha256", "nonce_base64", "wrapped_recovery_key_base64", "encrypted_private_key_base64"], "recovery envelope")
    require(value["schema"] == "settlement-recovery-envelope-v2", "invalid recovery envelope schema")
    require(canonical_envelope(value) == envelope_bytes, "recovery envelope encoding is not canonical")
    aad = envelope_aad(policy, hashlib.sha256(active_der).hexdigest())
    require(value["aad_sha256"] == hashlib.sha256(aad).hexdigest(), "recovery envelope AAD digest mismatch")
    nonce = strict_b64(value["nonce_base64"], "envelope nonce")
    wrapped = strict_b64(value["wrapped_recovery_key_base64"], "wrapped recovery key")
    encrypted = strict_b64(value["encrypted_private_key_base64"], "encrypted private key")
    require(len(nonce) == 12, "recovery envelope nonce must be 12 bytes")
    require(len(wrapped) == (escrow_certificate.public_key().key_size + 7) // 8, "wrapped recovery key length mismatch")
    require(len(encrypted) > 16, "encrypted private key is too short")
    recovery_key = decrypt_oaep(policy, wrapped)
    require(len(recovery_key) == 32, "recovered envelope key is not 32 bytes")
    try:
        private_der = AESGCM(recovery_key).decrypt(nonce, encrypted, aad)
    except Exception as exc:
        raise CeremonyError("recovery envelope AES-GCM authentication failed") from exc
    try:
        active_key = serialization.load_der_private_key(private_der, password=None)
    except (ValueError, TypeError) as exc:
        raise CeremonyError("recovery envelope does not contain a PKCS#8 private key") from exc
    require(isinstance(active_key, rsa.RSAPrivateKey) and active_key.key_size >= 2048, "recovery envelope private key is invalid")
    canonical_private = active_key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    require(canonical_private == private_der, "recovery envelope PKCS#8 is not canonical")
    require(active_key.public_key().public_numbers() == active_certificate.public_key().public_numbers(), "recovery envelope key does not match active certificate")
    if staged_key is not None:
        require(staged_key.private_numbers() == active_key.private_numbers(), "staged key conflicts with recovery envelope")
    return recovery_key, active_key, aad


def continuity_payload(policy, active_digest, envelope_digest):
    return (
        "settlement-rotation-continuity-v2\n"
        f"epoch={policy['epoch']}\n"
        f"retiring_key_id={policy['retiring']['id']}\n"
        f"active_key_id={policy['active']['id']}\n"
        f"active_certificate_sha256={active_digest}\n"
        f"recovery_envelope_sha256={envelope_digest}\n"
    ).encode("utf-8")


def receipt_payload(policy, signature_digest, envelope_digest):
    return (
        "settlement-escrow-receipt-v2\n"
        f"epoch={policy['epoch']}\n"
        f"primary_token_label={policy['primary_token']['label']}\n"
        f"escrow_token_label={policy['escrow_token']['label']}\n"
        f"escrow_key_id={policy['escrow']['id']}\n"
        f"continuity_signature_sha256={signature_digest}\n"
        f"recovery_envelope_sha256={envelope_digest}\n"
    ).encode("utf-8")


def evidence_bytes(session, handle, definition, description):
    object_id = bytes.fromhex(definition["object_id"])
    attrs = session.getAttributeValue(
        handle,
        [PyKCS11.CKA_CLASS, PyKCS11.CKA_TOKEN, PyKCS11.CKA_PRIVATE, PyKCS11.CKA_LABEL, PyKCS11.CKA_OBJECT_ID, PyKCS11.CKA_APPLICATION, PyKCS11.CKA_VALUE],
    )
    require(attrs[0] == PyKCS11.CKO_DATA and attrs[1] is True and attrs[2] is False, f"invalid {description} attributes")
    require(attrs[3] == definition["label"] and as_bytes(attrs[4]) == object_id and attrs[5] == definition["application"], f"invalid {description} identity")
    return as_bytes(attrs[6])


def validate_active_private(session, handle, policy, certificate):
    attrs = session.getAttributeValue(
        handle,
        [
            PyKCS11.CKA_CLASS,
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
    require(attrs[:11] == [PyKCS11.CKO_PRIVATE_KEY, PyKCS11.CKK_RSA, True, True, True, False, True, False, False, False, False], "active private key attributes violate policy")
    require(mechanism_values(attrs[11]) == (PyKCS11.CKM_SHA256_RSA_PKCS,), "active private key mechanism restriction violates policy")
    probe = b"active-key-binding-v2\n"
    try:
        signature = as_bytes(session.sign(handle, probe, PyKCS11.Mechanism(PyKCS11.CKM_SHA256_RSA_PKCS)))
    except PyKCS11.PyKCS11Error as exc:
        raise CeremonyError("active private key cannot sign") from exc
    verify_signature(certificate, signature, probe, "active private key certificate binding")
    try:
        session.sign(handle, b"raw-rsa", PyKCS11.Mechanism(PyKCS11.CKM_RSA_PKCS))
    except PyKCS11.PyKCS11Error:
        pass
    else:
        raise CeremonyError("active private key permits CKM_RSA_PKCS")


def validate_recovery(session, handle, policy, recovery_key, envelope_digest):
    attrs = session.getAttributeValue(
        handle,
        [
            PyKCS11.CKA_CLASS,
            PyKCS11.CKA_KEY_TYPE,
            PyKCS11.CKA_TOKEN,
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
            PyKCS11.CKA_VALUE_LEN,
            PyKCS11.CKA_ALLOWED_MECHANISMS,
        ],
    )
    expected = [PyKCS11.CKO_SECRET_KEY, PyKCS11.CKK_AES, True, True, True, False, True, False, False, False, False, False, False, 32]
    require(attrs[:14] == expected, "recovery key attributes violate policy")
    require(mechanism_values(attrs[14]) == (PyKCS11.CKM_AES_KEY_WRAP,), "recovery key mechanism restriction violates policy")
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
        wrapped = as_bytes(session.wrapKey(handle, probe, PyKCS11.Mechanism(PyKCS11.CKM_AES_KEY_WRAP)))
    except PyKCS11.PyKCS11Error as exc:
        raise CeremonyError("recovery key cannot wrap with AES-KEY-WRAP") from exc
    finally:
        session.destroyObject(probe)
    try:
        unwrapped = aes_key_unwrap(recovery_key, wrapped)
    except Exception as exc:
        raise CeremonyError("recovery key does not match recovery envelope") from exc
    require(unwrapped == probe_value, "recovery key does not match recovery envelope")


def integer_bytes(value):
    return list(value.to_bytes((value.bit_length() + 7) // 8, "big"))


def private_template(key, policy):
    numbers = key.private_numbers()
    public = numbers.public_numbers
    return [
        (PyKCS11.CKA_CLASS, PyKCS11.CKO_PRIVATE_KEY),
        (PyKCS11.CKA_KEY_TYPE, PyKCS11.CKK_RSA),
        (PyKCS11.CKA_TOKEN, True),
        (PyKCS11.CKA_PRIVATE, True),
        (PyKCS11.CKA_LABEL, policy["active"]["private_label"]),
        (PyKCS11.CKA_ID, bytes.fromhex(policy["active"]["id"])),
        (PyKCS11.CKA_SENSITIVE, True),
        (PyKCS11.CKA_EXTRACTABLE, False),
        (PyKCS11.CKA_SIGN, True),
        (PyKCS11.CKA_SIGN_RECOVER, False),
        (PyKCS11.CKA_DECRYPT, False),
        (PyKCS11.CKA_UNWRAP, False),
        (PyKCS11.CKA_DERIVE, False),
        (PyKCS11.CKA_ALLOWED_MECHANISMS, struct.pack("<Q", PyKCS11.CKM_SHA256_RSA_PKCS)),
        (PyKCS11.CKA_MODULUS, integer_bytes(public.n)),
        (PyKCS11.CKA_PUBLIC_EXPONENT, integer_bytes(public.e)),
        (PyKCS11.CKA_PRIVATE_EXPONENT, integer_bytes(numbers.d)),
        (PyKCS11.CKA_PRIME_1, integer_bytes(numbers.p)),
        (PyKCS11.CKA_PRIME_2, integer_bytes(numbers.q)),
        (PyKCS11.CKA_EXPONENT_1, integer_bytes(numbers.dmp1)),
        (PyKCS11.CKA_EXPONENT_2, integer_bytes(numbers.dmq1)),
        (PyKCS11.CKA_COEFFICIENT, integer_bytes(numbers.iqmp)),
    ]


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


def recovery_template(policy, recovery_key):
    return [
        (PyKCS11.CKA_CLASS, PyKCS11.CKO_SECRET_KEY),
        (PyKCS11.CKA_KEY_TYPE, PyKCS11.CKK_AES),
        (PyKCS11.CKA_TOKEN, True),
        (PyKCS11.CKA_PRIVATE, True),
        (PyKCS11.CKA_LABEL, policy["recovery"]["label"]),
        (PyKCS11.CKA_ID, bytes.fromhex(policy["recovery"]["id"])),
        (PyKCS11.CKA_VALUE, list(recovery_key)),
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


def validate_primary_final(session, policy, state, active_certificate, active_der, escrow_certificate):
    retiring_certificate, retiring_der = certificate_bytes(
        session,
        state["retiring_certificate"],
        bytes.fromhex(policy["retiring"]["id"]),
        policy["retiring"]["certificate_label"],
        "retiring certificate",
    )
    active_token_certificate, active_token_der = certificate_bytes(
        session,
        state["active_certificate"],
        bytes.fromhex(policy["active"]["id"]),
        policy["active"]["certificate_label"],
        "active certificate",
    )
    require(active_token_der == active_der, "active token certificate conflicts with incoming certificate")
    envelope_bytes = evidence_bytes(session, state["envelope"], policy["envelope"], "recovery envelope")
    recovery_key, recovered_active_key, aad = decode_envelope(policy, envelope_bytes, escrow_certificate, active_certificate, active_der, None)
    envelope_digest = hashlib.sha256(envelope_bytes).hexdigest()
    continuity = evidence_bytes(session, state["continuity"], policy["continuity"], "continuity evidence")
    continuity_bytes = continuity_payload(policy, hashlib.sha256(active_der).hexdigest(), envelope_digest)
    verify_signature(retiring_certificate, continuity, continuity_bytes, "continuity signature")
    receipt = evidence_bytes(session, state["receipt"], policy["receipt"], "escrow receipt")
    receipt_bytes = receipt_payload(policy, hashlib.sha256(continuity).hexdigest(), envelope_digest)
    verify_signature(escrow_certificate, receipt, receipt_bytes, "escrow receipt signature")
    validate_active_private(session, state["active_private"], policy, active_token_certificate)
    require(recovered_active_key.public_key().public_numbers() == active_token_certificate.public_key().public_numbers(), "active key differs from recovery envelope")
    validate_recovery(session, state["recovery"], policy, recovery_key, envelope_digest)
    return {
        "retiring_der": retiring_der,
        "active_der": active_token_der,
        "envelope": envelope_bytes,
        "continuity": continuity,
        "receipt": receipt,
        "continuity_payload": continuity_bytes,
        "receipt_payload": receipt_bytes,
        "aad": aad,
    }


def reconcile(policy_path, stage_path):
    policy = read_json(policy_path)
    validate_policy(policy)
    active_certificate, active_der = load_certificate(policy["active"]["certificate_path"], "incoming certificate")
    staged_key = load_optional_private_key(policy["active"]["private_key_path"], active_certificate)

    library = PyKCS11.PyKCS11Lib()
    try:
        library.load(MODULE)
    except PyKCS11.PyKCS11Error as exc:
        raise CeremonyError("cannot load the PKCS#11 module") from exc
    primary_session = None
    escrow_session = None
    try:
        primary_slot, primary_session = open_logged_session(library, policy["primary_token"])
        escrow_slot, escrow_session = open_logged_session(library, policy["escrow_token"])
        require(primary_slot != escrow_slot, "primary and escrow policies resolved to the same token")
        primary = inventory(primary_session, policy, "primary")
        escrow = inventory(escrow_session, policy, "escrow")
        require(escrow["escrow_certificate"] is not None and escrow["escrow_private"] is not None, "escrow token is missing managed custody objects")
        escrow_certificate, escrow_der = certificate_bytes(
            escrow_session,
            escrow["escrow_certificate"],
            bytes.fromhex(policy["escrow"]["id"]),
            policy["escrow"]["certificate_label"],
            "escrow certificate",
        )
        validate_escrow_private(escrow_session, escrow["escrow_private"], escrow_certificate)

        require(primary["retiring_certificate"] is not None, "retiring certificate is missing")
        retiring_certificate, retiring_der = certificate_bytes(
            primary_session,
            primary["retiring_certificate"],
            bytes.fromhex(policy["retiring"]["id"]),
            policy["retiring"]["certificate_label"],
            "retiring certificate",
        )
        if primary["retiring_private"] is not None:
            validate_retiring_private(primary_session, primary["retiring_private"], policy, retiring_certificate)

        if primary["active_certificate"] is not None:
            token_active_certificate, token_active_der = certificate_bytes(
                primary_session,
                primary["active_certificate"],
                bytes.fromhex(policy["active"]["id"]),
                policy["active"]["certificate_label"],
                "active certificate",
            )
            require(token_active_der == active_der, "active token certificate conflicts with incoming certificate")
        else:
            token_active_certificate = active_certificate
        if primary["active_private"] is not None:
            validate_active_private(primary_session, primary["active_private"], policy, token_active_certificate)

        if primary["envelope"] is not None:
            envelope_bytes = evidence_bytes(primary_session, primary["envelope"], policy["envelope"], "recovery envelope")
        else:
            require(staged_key is not None, "recovery envelope and staged private key are both absent")
            envelope_bytes = build_envelope(policy, escrow_certificate, active_der, staged_key)
        recovery_key, recovered_active_key, aad = decode_envelope(
            policy,
            envelope_bytes,
            escrow_certificate,
            active_certificate,
            active_der,
            staged_key,
        )
        envelope_digest = hashlib.sha256(envelope_bytes).hexdigest()

        if primary["recovery"] is not None:
            validate_recovery(primary_session, primary["recovery"], policy, recovery_key, envelope_digest)
        continuity_bytes = continuity_payload(policy, hashlib.sha256(active_der).hexdigest(), envelope_digest)
        if primary["continuity"] is not None:
            continuity = evidence_bytes(primary_session, primary["continuity"], policy["continuity"], "continuity evidence")
            verify_signature(retiring_certificate, continuity, continuity_bytes, "continuity signature")
        else:
            require(primary["retiring_private"] is not None, "irrecoverable state: retiring key and continuity evidence are absent")
            try:
                continuity = as_bytes(
                    primary_session.sign(
                        primary["retiring_private"],
                        continuity_bytes,
                        PyKCS11.Mechanism(PyKCS11.CKM_SHA256_RSA_PKCS),
                    )
                )
            except PyKCS11.PyKCS11Error as exc:
                raise CeremonyError("retiring private key cannot create continuity evidence") from exc
            verify_signature(retiring_certificate, continuity, continuity_bytes, "continuity signature")

        receipt_bytes = receipt_payload(policy, hashlib.sha256(continuity).hexdigest(), envelope_digest)
        if primary["receipt"] is not None:
            receipt = evidence_bytes(primary_session, primary["receipt"], policy["receipt"], "escrow receipt")
            verify_signature(escrow_certificate, receipt, receipt_bytes, "escrow receipt signature")
        else:
            try:
                receipt = as_bytes(
                    escrow_session.sign(
                        escrow["escrow_private"],
                        receipt_bytes,
                        PyKCS11.Mechanism(PyKCS11.CKM_SHA256_RSA_PKCS),
                    )
                )
            except PyKCS11.PyKCS11Error as exc:
                raise CeremonyError("escrow private key cannot create receipt") from exc
            verify_signature(escrow_certificate, receipt, receipt_bytes, "escrow receipt signature")

        if primary["envelope"] is None:
            primary_session.createObject(evidence_template(policy["envelope"], envelope_bytes))
        if primary["continuity"] is None:
            primary_session.createObject(evidence_template(policy["continuity"], continuity))
        if primary["receipt"] is None:
            primary_session.createObject(evidence_template(policy["receipt"], receipt))
        if primary["active_certificate"] is None:
            primary_session.createObject(
                certificate_template(active_certificate, active_der, bytes.fromhex(policy["active"]["id"]), policy["active"]["certificate_label"])
            )
        if primary["active_private"] is None:
            primary_session.createObject(private_template(recovered_active_key, policy))
        if primary["recovery"] is None:
            primary_session.createObject(recovery_template(policy, recovery_key))

        primary = inventory(primary_session, policy, "primary")
        escrow_after = inventory(escrow_session, policy, "escrow")
        require(all(primary[name] is not None for name in ("retiring_certificate", "active_certificate", "active_private", "recovery", "envelope", "continuity", "receipt")), "rotation did not create every final object")
        require(escrow_after["escrow_certificate"] is not None and escrow_after["escrow_private"] is not None, "escrow custody changed during rotation")
        live = validate_primary_final(primary_session, policy, primary, active_certificate, active_der, escrow_certificate)
        require(live["envelope"] == envelope_bytes and live["continuity"] == continuity and live["receipt"] == receipt, "evidence changed during reconciliation")

        if primary["retiring_private"] is not None:
            primary_session.destroyObject(primary["retiring_private"])
        primary = inventory(primary_session, policy, "primary")
        require(primary["retiring_private"] is None, "retiring private key could not be destroyed")
        live = validate_primary_final(primary_session, policy, primary, active_certificate, active_der, escrow_certificate)
        escrow_final = inventory(escrow_session, policy, "escrow")
        require(escrow_final["escrow_certificate"] is not None and escrow_final["escrow_private"] is not None, "escrow custody changed during rotation")

        attestation = {
            "schema": "settlement-rotation-attestation-v2",
            "primary_token_label": policy["primary_token"]["label"],
            "escrow_token_label": policy["escrow_token"]["label"],
            "epoch": policy["epoch"],
            "retiring_key_id": policy["retiring"]["id"],
            "active_key_id": policy["active"]["id"],
            "recovery_key_id": policy["recovery"]["id"],
            "escrow_key_id": policy["escrow"]["id"],
            "envelope_object_id": policy["envelope"]["object_id"],
            "continuity_object_id": policy["continuity"]["object_id"],
            "receipt_object_id": policy["receipt"]["object_id"],
            "retiring_certificate_sha256": hashlib.sha256(live["retiring_der"]).hexdigest(),
            "active_certificate_sha256": hashlib.sha256(live["active_der"]).hexdigest(),
            "escrow_certificate_sha256": hashlib.sha256(escrow_der).hexdigest(),
            "recovery_envelope_sha256": hashlib.sha256(live["envelope"]).hexdigest(),
            "continuity_payload_sha256": hashlib.sha256(live["continuity_payload"]).hexdigest(),
            "receipt_payload_sha256": hashlib.sha256(live["receipt_payload"]).hexdigest(),
            "continuity_signature_base64": base64.b64encode(live["continuity"]).decode("ascii"),
            "escrow_receipt_signature_base64": base64.b64encode(live["receipt"]).decode("ascii"),
        }
        with open(stage_path, "w", encoding="utf-8") as handle:
            json.dump(attestation, handle, indent=2)
            handle.write("\n")
    finally:
        for session in (escrow_session, primary_session):
            if session is not None:
                try:
                    session.logout()
                except PyKCS11.PyKCS11Error:
                    pass
                try:
                    session.closeSession()
                except PyKCS11.PyKCS11Error:
                    pass


def main():
    if len(sys.argv) != 3:
        print("rotate_ceremony: internal helper received invalid arguments", file=sys.stderr)
        return 2
    try:
        reconcile(sys.argv[1], sys.argv[2])
        return 0
    except CeremonyError as exc:
        print(f"rotate_ceremony: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"rotate_ceremony: provisioning failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
