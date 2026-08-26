"""Digest helpers shared by operator tooling and offline checks."""

from __future__ import annotations

import hashlib


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_raw(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def witness_hex(visits: list[int], edge_hash: bytes) -> str:
    buf = bytearray()
    for v in visits:
        buf.extend(int(v).to_bytes(2, "little", signed=False))
    buf.extend(edge_hash)
    return sha256_hex(buf)


def edge_hash_raw(lines: list[str]) -> bytes:
    blob = "\n".join(sorted(lines)).encode("utf-8")
    return sha256_raw(blob)
