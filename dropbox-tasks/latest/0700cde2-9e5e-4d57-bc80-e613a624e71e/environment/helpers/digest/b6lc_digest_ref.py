"""Digest helpers for beta-six lattice chronicle fuse pipeline.

Authoritative phase_seal preimage is seven pipe-separated fields including
audit_commitment — see /app/docs/walk-seal-bind.md.
"""
from __future__ import annotations

import hashlib
import json


def stable_sha256(obj: dict) -> str:
    """SHA-256 of compact sorted-key JSON (Perl JSON::PP key-ordered style)."""
    raw = json.dumps(obj, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def phase_bind(
    capture_digest: str,
    snapshot_digest: str,
    epoch: int,
    bind_digest: str,
    spine_digest: str,
) -> str:
    """Emit seal contract: capture|snapshot|epoch|bind|spine."""
    body = (
        f"{capture_digest}|{snapshot_digest}|{epoch}|{bind_digest}|{spine_digest}"
    )
    return hashlib.sha256(body.encode()).hexdigest()
