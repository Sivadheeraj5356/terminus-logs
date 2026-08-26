"""Phase seal bind helpers for polymorph walk chronicle."""
from __future__ import annotations

import hashlib


def walk_phase_bind(
    capture_digest: str,
    snapshot_digest: str,
    epoch: int,
    bind_digest: str,
    spine_digest: str,
) -> str:
    """Five-field phase_seal preimage matching /app/docs/walk-seal-bind.md."""
    body = (
        f"{capture_digest}|{snapshot_digest}|{epoch}|{bind_digest}|{spine_digest}"
    )
    return hashlib.sha256(body.encode()).hexdigest()
