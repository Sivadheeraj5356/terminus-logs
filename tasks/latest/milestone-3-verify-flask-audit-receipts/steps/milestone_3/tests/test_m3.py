"""Tests for milestone 3: Verify Flask Audit Receipts.

Run alone with: pytest tests/test_m3.py
Exercises the agent's transparency-log API directly via its Flask test client.
"""

import base64
import hashlib
import json
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

sys.path.insert(0, "/app/transparency")

GENESIS = "0" * 64


def _canonical_hash(obj):
    canon = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _recompute_entry_hash(entry):
    payload = json.dumps(
        {
            "index": entry["index"],
            "manifest_hash": entry["manifest_hash"],
            "prev_hash": entry["prev_hash"],
            "signature": entry["signature"],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _keypair():
    priv = Ed25519PrivateKey.generate()
    pub_pem = priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return priv, pub_pem


def _sign(priv, manifest):
    digest = _canonical_hash(manifest)
    return base64.b64encode(priv.sign(digest.encode("ascii"))).decode()


@pytest.fixture()
def client():
    from app import create_app

    return create_app().test_client()


class TestMilestone3:
    def test_modules_present(self):
        """The Flask app.py and log.py modules exist at /app/transparency."""
        assert Path("/app/transparency/app.py").exists()
        assert Path("/app/transparency/log.py").exists()

    def test_submit_returns_chained_receipts(self, client):
        """Posting signatures returns append-only receipts whose prev_hash chains to the previous entry_hash."""
        priv, pub_pem = _keypair()
        m0 = {"name": "p", "version": "1"}
        m1 = {"name": "p", "version": "2"}

        r0 = client.post("/signatures", json={
            "manifest": m0, "signature": _sign(priv, m0), "public_key_pem": pub_pem})
        assert r0.status_code == 200
        e0 = r0.get_json()["receipt"]
        assert e0["index"] == 0
        assert e0["prev_hash"] == GENESIS

        r1 = client.post("/signatures", json={
            "manifest": m1, "signature": _sign(priv, m1), "public_key_pem": pub_pem})
        assert r1.status_code == 200
        e1 = r1.get_json()["receipt"]
        assert e1["index"] == 1
        # append-only chain: entry 1 commits to entry 0's hash
        assert e1["prev_hash"] == e0["entry_hash"]

    def test_audit_chain_valid(self, client):
        """The /audit endpoint returns all entries with chain_valid true."""
        priv, pub_pem = _keypair()
        for v in ("1", "2", "3"):
            m = {"name": "p", "version": v}
            client.post("/signatures", json={
                "manifest": m, "signature": _sign(priv, m), "public_key_pem": pub_pem})
        audit = client.get("/audit").get_json()
        assert len(audit["entries"]) == 3
        assert audit["chain_valid"] is True

    def test_entry_hash_is_recomputed_not_arbitrary(self, client):
        """entry_hash is the SHA-256 over the canonical committed fields, recomputable and used to chain."""
        # Anti-cheat: entry_hash must be the SHA-256 over the canonical
        # {index, manifest_hash, prev_hash, signature}. A server that emits
        # arbitrary hex (only kept self-consistent for chaining) is rejected.
        priv, pub_pem = _keypair()
        m0 = {"name": "p", "version": "1"}
        m1 = {"name": "p", "version": "2"}
        sig0 = _sign(priv, m0)
        e0 = client.post("/signatures", json={
            "manifest": m0, "signature": sig0, "public_key_pem": pub_pem}).get_json()["receipt"]
        e1 = client.post("/signatures", json={
            "manifest": m1, "signature": _sign(priv, m1), "public_key_pem": pub_pem}).get_json()["receipt"]

        # Receipt fields are exactly what was committed.
        assert e0["index"] == 0
        assert e0["prev_hash"] == GENESIS
        assert e0["manifest_hash"] == _canonical_hash(m0)
        assert e0["signature"] == sig0
        # entry_hash must equal the independent recomputation.
        assert e0["entry_hash"] == _recompute_entry_hash(e0)
        assert e1["entry_hash"] == _recompute_entry_hash(e1)
        # ...and the chain must link via the real recomputed hash.
        assert e1["prev_hash"] == _recompute_entry_hash(e0)

    def test_invalid_signature_rejected(self, client):
        """A submission with an invalid Ed25519 signature is rejected with HTTP 400."""
        priv, pub_pem = _keypair()
        m = {"name": "p", "version": "1"}
        bad_sig = base64.b64encode(b"\x00" * 64).decode()
        r = client.post("/signatures", json={
            "manifest": m, "signature": bad_sig, "public_key_pem": pub_pem})
        assert r.status_code == 400

    def test_tampered_manifest_hash_rejected(self, client):
        """A supplied manifest_hash that mismatches the server computation is rejected with HTTP 400."""
        priv, pub_pem = _keypair()
        m = {"name": "p", "version": "1"}
        r = client.post("/signatures", json={
            "manifest": m, "signature": _sign(priv, m), "public_key_pem": pub_pem,
            "manifest_hash": "deadbeef" * 8})
        assert r.status_code == 400

    def test_replay_rejected(self, client):
        """A replayed manifest_hash/signature pair is rejected with HTTP 409."""
        priv, pub_pem = _keypair()
        m = {"name": "p", "version": "1"}
        payload = {"manifest": m, "signature": _sign(priv, m), "public_key_pem": pub_pem}
        assert client.post("/signatures", json=payload).status_code == 200
        assert client.post("/signatures", json=payload).status_code == 409

    def test_receipt_retrieval(self, client):
        """GET /receipts/<index> returns the entry for a valid index and 404 for a missing one."""
        priv, pub_pem = _keypair()
        m = {"name": "p", "version": "1"}
        client.post("/signatures", json={
            "manifest": m, "signature": _sign(priv, m), "public_key_pem": pub_pem})
        r = client.get("/receipts/0")
        assert r.status_code == 200
        assert r.get_json()["receipt"]["index"] == 0
        assert client.get("/receipts/99").status_code == 404

    def test_log_path_persists_and_reloads(self, tmp_path):
        """A log_path-backed app persists entries and a new app over the same path reloads them."""
        # When create_app is given a log_path, entries must be persisted and a
        # brand-new app over the SAME path must reload them (not start empty).
        from app import create_app

        log_file = tmp_path / "audit_log.jsonl"
        priv, pub_pem = _keypair()
        m = {"name": "persist", "version": "1"}

        c1 = create_app(log_path=str(log_file)).test_client()
        r = c1.post("/signatures", json={
            "manifest": m, "signature": _sign(priv, m), "public_key_pem": pub_pem})
        assert r.status_code == 200
        e = r.get_json()["receipt"]

        c2 = create_app(log_path=str(log_file)).test_client()
        audit = c2.get("/audit").get_json()
        assert len(audit["entries"]) == 1, "reloaded app must see the persisted entry"
        assert audit["chain_valid"] is True
        assert audit["entries"][0]["entry_hash"] == e["entry_hash"]
        # ...and the reloaded entry is retrievable and recomputes correctly.
        r2 = c2.get("/receipts/0")
        assert r2.status_code == 200
        reloaded = r2.get_json()["receipt"]
        assert reloaded["manifest_hash"] == e["manifest_hash"]
        assert reloaded["entry_hash"] == _recompute_entry_hash(reloaded)

    def test_default_log_path_is_in_memory_and_isolated(self):
        """log_path=None gives a fresh, isolated, empty in-memory log per app with no shared state."""
        # log_path=None must give a fresh, isolated, empty in-memory log per
        # app: a second default app must not observe the first app's entry.
        from app import create_app

        priv, pub_pem = _keypair()
        m = {"name": "iso", "version": "1"}
        c1 = create_app().test_client()
        assert c1.post("/signatures", json={
            "manifest": m, "signature": _sign(priv, m),
            "public_key_pem": pub_pem}).status_code == 200
        c2 = create_app().test_client()
        assert c2.get("/audit").get_json()["entries"] == [], \
            "a fresh default app must start empty (no shared/default on-disk log)"

    def test_oracle_demo_artifacts(self):
        """The demo receipt.json and audit.json correspond to /app/data/manifest.json with a valid chain."""
        receipt = Path("/app/out/receipt.json")
        audit = Path("/app/out/audit.json")
        assert receipt.exists() and audit.exists()
        audit_obj = json.loads(audit.read_text())
        assert audit_obj["chain_valid"] is True

        # The demo receipt must correspond to /app/data/manifest.json — not be a
        # placeholder. Its manifest_hash must equal the canonical hash of that
        # manifest, and its entry_hash must recompute from the committed fields.
        manifest = json.loads(Path("/app/data/manifest.json").read_text())
        entry = json.loads(receipt.read_text())["receipt"]
        assert entry["manifest_hash"] == _canonical_hash(manifest)
        assert entry["entry_hash"] == _recompute_entry_hash(entry)
        # The demo entry must actually be present in the persisted audit log.
        assert any(e["entry_hash"] == entry["entry_hash"] for e in audit_obj["entries"])
