"""Hex and big-endian binary helpers."""

from __future__ import annotations

import hashlib
import re

_HEX_RE = re.compile(r"^[0-9a-f]*$")


def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def decode_lower_hex(s: str) -> bytes:
    if not isinstance(s, str):
        raise ValueError("hex must be string")
    if len(s) % 2 != 0:
        raise ValueError("odd-length hex")
    if s.startswith("0x") or s.startswith("0X"):
        raise ValueError("hex must not include 0x prefix")
    if any(c.isupper() for c in s):
        raise ValueError("hex must be lowercase")
    if any(c.isspace() for c in s):
        raise ValueError("hex must not contain whitespace")
    if not _HEX_RE.fullmatch(s):
        raise ValueError("invalid hex")
    return bytes.fromhex(s)


def encode_lower_hex(data: bytes) -> str:
    return data.hex()


def require_exact_hex(s: str, nbytes: int) -> bytes:
    if len(s) != nbytes * 2:
        raise ValueError(f"expected {nbytes * 2} hex chars, got {len(s)}")
    return decode_lower_hex(s)


class Cursor:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 0

    def remaining(self) -> int:
        return len(self.data) - self.pos

    def finish(self) -> None:
        if self.pos != len(self.data):
            raise ValueError("trailing bytes")

    def read_exact(self, n: int) -> bytes:
        if self.remaining() < n:
            raise ValueError("truncated field")
        out = self.data[self.pos : self.pos + n]
        self.pos += n
        return out

    def read_u8(self) -> int:
        return self.read_exact(1)[0]

    def read_u16(self) -> int:
        return int.from_bytes(self.read_exact(2), "big")

    def read_u32(self) -> int:
        return int.from_bytes(self.read_exact(4), "big")

    def read_u64(self) -> int:
        return int.from_bytes(self.read_exact(8), "big")


def write_u8(v: int) -> bytes:
    return bytes([v & 0xFF])


def write_u16(v: int) -> bytes:
    return int(v).to_bytes(2, "big")


def write_u32(v: int) -> bytes:
    return int(v).to_bytes(4, "big")


def write_u64(v: int) -> bytes:
    return int(v).to_bytes(8, "big")
