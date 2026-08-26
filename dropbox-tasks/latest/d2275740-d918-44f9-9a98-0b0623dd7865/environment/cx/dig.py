"""Digest helpers shared with emit packing notes."""

from __future__ import annotations

import hashlib


def sha256_hex(parts: list[bytes]) -> str:
    h = hashlib.sha256()
    for part in parts:
        h.update(part)
    return h.hexdigest()
