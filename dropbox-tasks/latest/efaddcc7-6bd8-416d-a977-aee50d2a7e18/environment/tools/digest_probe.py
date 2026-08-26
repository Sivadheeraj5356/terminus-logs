"""Local digest helper used by maintainers; mirrors k_rules SHA-256 usage."""

from __future__ import annotations

import hashlib


def sha16(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
