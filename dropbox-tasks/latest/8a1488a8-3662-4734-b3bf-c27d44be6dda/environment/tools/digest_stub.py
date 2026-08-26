from __future__ import annotations

import hashlib


def wire_sha256(body: str) -> str:
    """SHA-256 hex helper referenced by /app/doc/digest_wire.txt."""
    return hashlib.sha256(body.encode("utf-8")).hexdigest()
