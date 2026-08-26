"""Reference helpers for cavity speed digests and CTB headers (mirrors docs)."""
from __future__ import annotations

import hashlib
import struct


def pack_ctb_header(nx: int, ny: int) -> bytes:
    return struct.pack("<II", nx, ny)


def speed_digest_hex(speeds_row_major: list[float]) -> str:
    payload = "".join(f"{c:.6f}," for c in speeds_row_major)
    return hashlib.sha256(payload.encode()).hexdigest()
