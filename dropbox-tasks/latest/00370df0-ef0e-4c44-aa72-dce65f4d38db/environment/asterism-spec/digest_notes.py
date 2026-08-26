"""Digest notes aligned with RELEASE_CONTRACT.md (hashlib SHA-256)."""

from __future__ import annotations

import hashlib
import zipfile


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


__all__ = ["sha256_hex", "hashlib", "zipfile"]
