"""Shared digest helpers for bracket desk harness probes.

Agents implement SHA-256 digests in PHP; this module mirrors the same
hashlib and sqlite3 contracts used when verifying store and snapshot digests.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any


def sha256_hex(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compact_json(obj: Any) -> str:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def count_table_rows(db_path: str, table: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    finally:
        conn.close()
