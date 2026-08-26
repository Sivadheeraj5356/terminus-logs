"""Tests for milestone 2: Sign with Ed25519 Keys.

Run alone with: pytest tests/test_m2.py
"""

import base64
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

CLI = "/app/transparency/cli.py"
KEY_DIR = Path("/app/keys")
OUT = Path("/app/out")


def _canonical_hash(obj):
    canon = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


class TestMilestone2:
    def test_milestone_1_persists(self):
        """Milestone-1 canonical.py and cli.py still exist in the shared container."""
        assert Path("/app/transparency/canonical.py").exists()
        assert Path(CLI).exists()

    def test_keys_module_exists(self):
        """The signing logic lives in the required flat module /app/transparency/keys.py."""
        # The signing logic must live in the required flat module path.
        assert Path("/app/transparency/keys.py").exists(), \
            "keys.py must exist at /app/transparency/keys.py"

    def test_keypair_generated(self):
        """keygen writes the private and public PEMs and the public key loads as an Ed25519 key."""
        assert (KEY_DIR / "ed25519_private.pem").exists()
        assert (KEY_DIR / "ed25519_public.pem").exists()
        # public key must be a valid Ed25519 key
        pub = serialization.load_pem_public_key((KEY_DIR / "ed25519_public.pem").read_bytes())
        assert isinstance(pub, Ed25519PublicKey)

    def test_private_key_is_pkcs8_unencrypted_ed25519(self):
        """The private key PEM is an unencrypted PKCS8 Ed25519 key."""
        # The instruction requires ed25519_private.pem to be an UNENCRYPTED
        # PKCS8 Ed25519 key. PKCS8 uses the "BEGIN PRIVATE KEY" PEM marker;
        # an encrypted key would say "BEGIN ENCRYPTED PRIVATE KEY", and a
        # legacy/SEC1 key would say "BEGIN EC PRIVATE KEY".
        pem = (KEY_DIR / "ed25519_private.pem").read_bytes()
        assert b"-----BEGIN PRIVATE KEY-----" in pem, \
            "private key must be PKCS8 (BEGIN PRIVATE KEY)"
        assert b"ENCRYPTED" not in pem, "private key must be unencrypted"
        # Must load with no password and be an Ed25519 private key.
        priv = serialization.load_pem_private_key(pem, password=None)
        assert isinstance(priv, Ed25519PrivateKey)

    def test_signature_verifies(self):
        """manifest.sig verifies under the public key over the ASCII hex digest of the manifest."""
        sig_b64 = (OUT / "manifest.sig").read_text().strip()
        manifest = json.loads(Path("/app/data/manifest.json").read_text())
        digest = _canonical_hash(manifest)
        pub = serialization.load_pem_public_key((KEY_DIR / "ed25519_public.pem").read_bytes())
        # Must not raise
        pub.verify(base64.b64decode(sig_b64), digest.encode("ascii"))

    def test_tampered_manifest_fails_verification(self):
        """A tampered manifest's digest no longer verifies against the stored signature."""
        sig_b64 = (OUT / "manifest.sig").read_text().strip()
        manifest = json.loads(Path("/app/data/manifest.json").read_text())
        manifest["version"] = "9.9.9-tampered"
        bad_digest = _canonical_hash(manifest)
        pub = serialization.load_pem_public_key((KEY_DIR / "ed25519_public.pem").read_bytes())
        try:
            pub.verify(base64.b64decode(sig_b64), bad_digest.encode("ascii"))
            raise AssertionError("tampered manifest must not verify")
        except InvalidSignature:
            pass

    def test_cli_verify_subcommand(self, tmp_path):
        """The verify subcommand prints exactly 'valid' and exits 0 for a good signature."""
        # The agent's own verify path must report validity correctly.
        r = subprocess.run(
            [sys.executable, CLI, "verify", "/app/data/manifest.json",
             "--key-dir", str(KEY_DIR), "--sig", str(OUT / "manifest.sig")],
            capture_output=True, text=True,
        )
        assert r.returncode == 0
        # Exact match, not substring: "invalid" contains "valid", so a substring
        # check (or a hardcoded print("valid")) must not be accepted here.
        assert r.stdout.strip() == "valid"

    def test_cli_verify_rejects_tampered_manifest(self, tmp_path):
        """verify prints exactly 'invalid' and exits non-zero when the manifest was tampered."""
        # Anti-cheat: verifying the VALID signature against a TAMPERED manifest
        # must report "invalid" exactly and exit non-zero. A stub that always
        # prints "valid" / always exits 0 fails this.
        manifest = json.loads(Path("/app/data/manifest.json").read_text())
        manifest["version"] = "9.9.9-tampered"
        tampered = tmp_path / "tampered.json"
        tampered.write_text(json.dumps(manifest))
        r = subprocess.run(
            [sys.executable, CLI, "verify", str(tampered),
             "--key-dir", str(KEY_DIR), "--sig", str(OUT / "manifest.sig")],
            capture_output=True, text=True,
        )
        assert r.returncode != 0
        assert r.stdout.strip() == "invalid"
