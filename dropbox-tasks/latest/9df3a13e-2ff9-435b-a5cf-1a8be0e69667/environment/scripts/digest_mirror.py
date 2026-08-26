"""SHA-256 helpers mirroring chalk and ledger digest contracts (hashlib)."""

from __future__ import annotations

import hashlib
import json


def sha256_hex(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def compact_json_digest(obj: object) -> str:
    raw = json.dumps(obj, separators=(",", ":"), ensure_ascii=True).encode()
    return sha256_hex(raw)
