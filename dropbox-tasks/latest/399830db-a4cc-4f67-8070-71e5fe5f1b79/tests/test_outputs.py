"""Verifier for the Rust seal_authz cryptographic gate outputs."""

from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
import subprocess
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

OUTPUT = Path("/app/output")
ATTESTATION = OUTPUT / "seal_attestation.json"
ATTESTATION_SIG = OUTPUT / "seal_attestation.sig"
DB_PATH = OUTPUT / "seal_authz.db"
BIN = Path("/app/bin/seal_authz")
SEALED = Path("/app/data/sealed")
POLICY = Path("/app/data/policy.json")
ARCHIVE_PUB = Path("/app/data/keys/archive_verify.pub")
REGISTRY_PUB = Path("/app/data/keys/registry_verify.pub")
DEK_PATH = Path("/app/data/keys/label_dek.bin")

EXPECTED_LABELS = {
    "MSR-0001": "BRAF_V600E",
    "MSR-0002": "KRAS_G12D",
    "MSR-0003": "TP53_R175H",
    "MSR-0004": "MYC_AMP",
    "MSR-0005": "ERBB2_AMP",
    "MSR-0006": "CDKN2A_DEL",
}

EXPECTED_AUTHORIZED = {
    "copy_number_alteration": ["MSR-0004", "MSR-0005", "MSR-0006"],
    "epigenetic_change": ["MSR-0009", "MSR-0010"],
    "point_mutation": ["MSR-0001", "MSR-0002", "MSR-0003"],
    "translocation": ["MSR-0007", "MSR-0008"],
}

EXPECTED_DENIED = ["MSR-0011", "MSR-0012"]
PATIENT_TOKENS = [
    "PT-ALPHA-771",
    "PT-BETA-902",
    "PT-GAMMA-114",
    "PT-DELTA-220",
    "PT-EPSILON-331",
    "PT-ZETA-442",
    "PT-ETA-553",
    "PT-THETA-664",
    "PT-IOTA-775",
    "PT-KAPPA-886",
    "PT-LAMBDA-997",
    "PT-MU-008",
]


def _load_attestation() -> dict:
    return json.loads(ATTESTATION.read_text(encoding="utf-8"))


def _canonical(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def test_binary_exists_and_is_executable():
    """The seal_authz binary must exist at /app/bin/seal_authz and be executable."""
    assert BIN.is_file(), f"missing binary {BIN}"
    assert BIN.stat().st_mode & 0o111, f"{BIN} is not executable"


def test_output_artifacts_exist():
    """Attestation JSON, signature file, and SQLite authz DB must be produced under /app/output."""
    assert ATTESTATION.is_file(), f"missing {ATTESTATION}"
    assert ATTESTATION_SIG.is_file(), f"missing {ATTESTATION_SIG}"
    assert DB_PATH.is_file(), f"missing {DB_PATH}"


def test_attestation_is_canonical_json():
    """seal_attestation.json must be canonical compact JSON with sorted object keys."""
    raw = ATTESTATION.read_text(encoding="utf-8")
    data = json.loads(raw)
    assert raw == _canonical(data), "attestation file bytes must equal canonical JSON serialization"


def test_attestation_schema_and_seeded_authorization():
    """Attestation must version=1 with deterministic authorized scopes and audit counters."""
    data = _load_attestation()
    assert data["version"] == 1
    assert data["audit"] == {"scanned": 12, "authenticated": 10, "denied": 2}
    assert data["denied"] == EXPECTED_DENIED

    cats = [g["category"] for g in data["authorized"]]
    assert cats == sorted(cats), "authorized must be sorted by category"
    assert cats == list(EXPECTED_AUTHORIZED.keys())

    for scope in data["authorized"]:
        cat = scope["category"]
        assert scope["report_ids"] == EXPECTED_AUTHORIZED[cat]
        assert scope["report_ids"] == sorted(scope["report_ids"])
        if cat in ("point_mutation", "copy_number_alteration"):
            assert "labels" in scope
            for rid in scope["report_ids"]:
                assert scope["labels"][rid] == EXPECTED_LABELS[rid]
        else:
            assert "labels" not in scope, f"{cat} must not expose decrypted labels"


def test_denied_invalid_signature_and_unauthorized_class():
    """MSR-0011 (bad signature) and MSR-0012 (unauthorized class) must appear only in denied."""
    data = _load_attestation()
    accepted_ids = {rid for g in data["authorized"] for rid in g["report_ids"]}
    assert "MSR-0011" in data["denied"]
    assert "MSR-0012" in data["denied"]
    assert "MSR-0011" not in accepted_ids
    assert "MSR-0012" not in accepted_ids


def test_patient_refs_never_leaked():
    """No patient_ref / PT-* token may appear in the attestation, signature, or SQLite database."""
    blobs = [
        ATTESTATION.read_bytes(),
        ATTESTATION_SIG.read_bytes(),
        DB_PATH.read_bytes(),
    ]
    for token in PATIENT_TOKENS:
        needle = token.encode("utf-8")
        for blob in blobs:
            assert needle not in blob, f"patient token {token} leaked into outputs"
    assert b"patient_ref" not in ATTESTATION.read_bytes()


def test_attestation_signature_verifies_with_registry_public_key():
    """seal_attestation.sig must be a valid ECDSA P-256 SHA-256 signature over the attestation bytes."""
    pub = serialization.load_pem_public_key(REGISTRY_PUB.read_bytes())
    sig = base64.b64decode(ATTESTATION_SIG.read_text(encoding="utf-8").strip())
    pub.verify(sig, ATTESTATION.read_bytes(), ec.ECDSA(hashes.SHA256()))


def test_sqlite_authentications_and_meta():
    """seal_authz.db must store authenticated rows, NULL labels for non-decrypt classes, and meta hashes."""
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            "SELECT report_id, category, label, verified FROM authentications ORDER BY report_id"
        ).fetchall()
        assert len(rows) == 10
        by_id = {r[0]: r for r in rows}
        for rid, label in EXPECTED_LABELS.items():
            assert by_id[rid][2] == label
            assert by_id[rid][3] == 1
        for rid in ("MSR-0007", "MSR-0008", "MSR-0009", "MSR-0010"):
            assert by_id[rid][2] is None
            assert by_id[rid][3] == 1

        meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
        assert meta["authenticated_count"] == "10"
        assert meta["denied_count"] == "2"
        expected_sha = hashlib.sha256(ATTESTATION.read_bytes()).hexdigest()
        assert meta["attestation_sha256"] == expected_sha
    finally:
        conn.close()


def test_label_dek_must_be_exactly_32_bytes():
    """The gate must exit non-zero when label_dek.bin is not exactly 32 bytes and leave outputs untouched."""
    assert BIN.is_file()
    original_attestation = ATTESTATION.read_bytes()
    original_sig = ATTESTATION_SIG.read_bytes()
    original_db = DB_PATH.read_bytes()
    original_dek = DEK_PATH.read_bytes()
    try:
        DEK_PATH.write_bytes(original_dek[:16])
        proc = subprocess.run([str(BIN)], capture_output=True, text=True, timeout=60)
        assert proc.returncode != 0, "gate must fail closed on short DEK"
        assert ATTESTATION.read_bytes() == original_attestation
        assert ATTESTATION_SIG.read_bytes() == original_sig
        assert DB_PATH.read_bytes() == original_db
    finally:
        DEK_PATH.write_bytes(original_dek)


def test_rerun_is_deterministic():
    """Re-running /app/bin/seal_authz must reproduce identical attestation bytes; new signature must still verify."""
    before = ATTESTATION.read_bytes()
    subprocess.run([str(BIN)], check=True, timeout=120)
    assert ATTESTATION.read_bytes() == before
    pub = serialization.load_pem_public_key(REGISTRY_PUB.read_bytes())
    sig = base64.b64decode(ATTESTATION_SIG.read_text(encoding="utf-8").strip())
    pub.verify(sig, before, ec.ECDSA(hashes.SHA256()))


def test_tampered_signature_is_denied_on_rerun():
    """If a previously authenticated claim signature is tampered, a re-run must move it into denied."""
    target = SEALED / "MSR-0001.json"
    backup = target.read_text(encoding="utf-8")
    try:
        rec = json.loads(backup)
        sig = rec["signature"]
        chars = list(sig)
        chars[20] = "A" if chars[20] != "A" else "B"
        rec["signature"] = "".join(chars)
        target.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")

        subprocess.run([str(BIN)], check=True, timeout=120)
        data = _load_attestation()
        assert "MSR-0001" in data["denied"]
        accepted_ids = {rid for g in data["authorized"] for rid in g["report_ids"]}
        assert "MSR-0001" not in accepted_ids
        assert data["audit"]["authenticated"] == 9
        assert data["audit"]["denied"] == 3
    finally:
        target.write_text(backup, encoding="utf-8")
        subprocess.run([str(BIN)], check=True, timeout=120)


def test_independent_aes_gcm_roundtrip_matches_attestation_labels():
    """Decrypting seeded ciphertexts with label_dek.bin must match attestation labels for decrypt-authorized classes."""
    dek = DEK_PATH.read_bytes()
    assert len(dek) == 32
    aesgcm = AESGCM(dek)
    data = _load_attestation()
    labels = {}
    for scope in data["authorized"]:
        if "labels" in scope:
            labels.update(scope["labels"])

    for rid, expected in EXPECTED_LABELS.items():
        rec = json.loads((SEALED / f"{rid}.json").read_text(encoding="utf-8"))
        nonce = base64.b64decode(rec["label_nonce"])
        ct = base64.b64decode(rec["label_ciphertext"])
        tag = base64.b64decode(rec["label_tag"])
        pt = aesgcm.decrypt(nonce, ct + tag, None).decode("utf-8")
        assert pt == expected
        assert labels[rid] == expected


def test_archive_signatures_validate_for_authenticated_claims():
    """Authenticated claims must verify against archive_verify.pub; denied MSR-0011 must not."""
    pub = serialization.load_pem_public_key(ARCHIVE_PUB.read_bytes())
    data = _load_attestation()
    accepted_ids = {rid for g in data["authorized"] for rid in g["report_ids"]}

    for path in sorted(SEALED.glob("*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        msg = (
            f"{rec['report_id']}|{rec['category']}|{rec['label_ciphertext']}|"
            f"{rec['label_nonce']}|{rec['label_tag']}"
        ).encode("utf-8")
        sig = base64.b64decode(rec["signature"])
        if rec["report_id"] in accepted_ids:
            pub.verify(sig, msg, ec.ECDSA(hashes.SHA256()))
        elif rec["report_id"] == "MSR-0011":
            try:
                pub.verify(sig, msg, ec.ECDSA(hashes.SHA256()))
                raise AssertionError("MSR-0011 signature unexpectedly valid")
            except Exception:
                pass


def test_policy_file_is_honored_for_decrypt_classes():
    """Only classes listed in policy decrypt_plaintext_for may expose plaintext labels in the attestation."""
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    data = _load_attestation()
    decrypt_for = set(policy["decrypt_plaintext_for"])
    for scope in data["authorized"]:
        if scope["category"] in decrypt_for:
            assert "labels" in scope and scope["labels"]
        else:
            assert "labels" not in scope


def test_recreate_after_delete_produces_identical_attestation():
    """Deleting output artifacts and re-running must recreate identical attestation bytes."""
    before = ATTESTATION.read_bytes()
    ATTESTATION.unlink()
    ATTESTATION_SIG.unlink()
    DB_PATH.unlink()
    subprocess.run([str(BIN)], check=True, timeout=120)
    assert ATTESTATION.read_bytes() == before
    pub = serialization.load_pem_public_key(REGISTRY_PUB.read_bytes())
    sig = base64.b64decode(ATTESTATION_SIG.read_text(encoding="utf-8").strip())
    pub.verify(sig, before, ec.ECDSA(hashes.SHA256()))
    assert DB_PATH.is_file()


def test_policy_decrypt_injection_exposes_new_labels():
    """Expanding decrypt_plaintext_for at runtime must decrypt and expose labels for that class."""
    backup = POLICY.read_text(encoding="utf-8")
    try:
        policy = json.loads(backup)
        if "epigenetic_change" not in policy["decrypt_plaintext_for"]:
            policy["decrypt_plaintext_for"].append("epigenetic_change")
        POLICY.write_text(json.dumps(policy, indent=2) + "\n", encoding="utf-8")
        subprocess.run([str(BIN)], check=True, timeout=120)
        data = _load_attestation()
        epi = next(g for g in data["authorized"] if g["category"] == "epigenetic_change")
        assert epi["labels"]["MSR-0009"] == "MGMT_METH"
        assert epi["labels"]["MSR-0010"] == "MLH1_METH"
        conn = sqlite3.connect(DB_PATH)
        try:
            rows = dict(
                conn.execute(
                    "SELECT report_id, label FROM authentications "
                    "WHERE report_id IN ('MSR-0009', 'MSR-0010')"
                ).fetchall()
            )
            assert rows["MSR-0009"] == "MGMT_METH"
            assert rows["MSR-0010"] == "MLH1_METH"
        finally:
            conn.close()
    finally:
        POLICY.write_text(backup, encoding="utf-8")
        subprocess.run([str(BIN)], check=True, timeout=120)


def test_policy_authorized_injection_denies_removed_class():
    """Removing a class from authorized_classes must deny previously authenticated claims in that class."""
    backup = POLICY.read_text(encoding="utf-8")
    try:
        policy = json.loads(backup)
        policy["authorized_classes"] = [
            c for c in policy["authorized_classes"] if c != "translocation"
        ]
        POLICY.write_text(json.dumps(policy, indent=2) + "\n", encoding="utf-8")
        subprocess.run([str(BIN)], check=True, timeout=120)
        data = _load_attestation()
        cats = {g["category"] for g in data["authorized"]}
        assert "translocation" not in cats
        assert "MSR-0007" in data["denied"]
        assert "MSR-0008" in data["denied"]
        assert data["audit"]["authenticated"] == 8
        assert data["audit"]["denied"] == 4
    finally:
        POLICY.write_text(backup, encoding="utf-8")
        subprocess.run([str(BIN)], check=True, timeout=120)
