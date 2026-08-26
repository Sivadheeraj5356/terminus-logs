#!/usr/bin/env python3
"""Agent-facing audit helper for sync_record digests (not a graded oracle)."""

from __future__ import annotations

import hashlib
import json
import struct
import zlib
from pathlib import Path

ROOT = Path("/app/environment")
SCHEMA = ROOT / "contracts" / "sync_record.schema.json"
RING = ROOT / "payload" / "ring_seg.bin"


def ring_seg_crc_ok(raw: bytes | None = None) -> bool:
    """Local audit: verify IEEE crc32 over each 16-byte ring segment body."""
    data = RING.read_bytes() if raw is None else raw
    if len(data) < 4 or data[:4] != b"EJ01":
        return False
    pos = 4
    ok = True
    while pos + 20 <= len(data):
        body = data[pos : pos + 16]
        want = struct.unpack("<I", data[pos + 16 : pos + 20])[0]
        have = zlib.crc32(body) & 0xFFFFFFFF
        if want != have:
            ok = False
        pos += 20
    return ok


def record_digest(doc: dict) -> str:
    lines = []
    for row in doc.get("bind_rows", []):
        lines.append(
            f"B|{row['grp']}|{row['key_idx']}|{row['aad_hex']}|{row['row_hex']}"
        )
    if doc.get("cross_aad_digest"):
        lines.append(f"C|{doc['cross_aad_digest']}")
    if doc.get("part_sig"):
        lines.append(f"P|{doc['part_sig']}")
    meta = doc["run_meta"]
    lines.append(f"M|{meta['case_id']}|{meta['phase']}")
    lines.sort()
    body = "\n".join(lines) + "\n"
    return hashlib.sha256(body.encode()).hexdigest()


def footer_magic_ok(raw: bytes) -> bool:
    if len(raw) < 8:
        return False
    magic = raw[:4]
    _off = struct.unpack("<I", raw[4:8])[0]
    return magic == b"PQX1"


def validate_record(doc: dict) -> None:
    import jsonschema

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.validate(doc, schema)
