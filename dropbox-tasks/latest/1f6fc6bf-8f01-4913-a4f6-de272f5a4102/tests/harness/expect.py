#!/usr/bin/env python3
"""Independent journal_digest evaluator for seeded conformance checks."""
from __future__ import annotations

import hashlib
from typing import Iterable


def journal_digest(rows: Iterable[tuple[int, int, str, int]]) -> str:
    """Rows are (socket_id, shard, event, round_index) tuples."""
    material = sorted(rows, key=lambda r: (r[3], r[0]))
    hasher = hashlib.sha256()
    for socket_id, shard, event, _round_index in material:
        hasher.update(socket_id.to_bytes(4, "little"))
        hasher.update(b"\x1f")
        hasher.update(shard.to_bytes(4, "little"))
        hasher.update(b"\x1f")
        hasher.update(event.encode())
    return hasher.hexdigest()
