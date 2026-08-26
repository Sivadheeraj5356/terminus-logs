"""Visible sha16 helper matching /app/docs/pol_contract.md Digests."""
from __future__ import annotations

import hashlib


def sha16(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]
