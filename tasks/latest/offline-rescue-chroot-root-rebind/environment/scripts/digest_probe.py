#!/usr/bin/env python3
"""Probe helpers for packaging digest materials (stdlib hashlib/struct)."""

from __future__ import annotations

import hashlib
import struct


def cache_digest(prefix: str, epoch: int, gen: int) -> str:
    blob = f"PREFIX={prefix}\nEPOCH={epoch}\nGEN={gen}\n".encode()
    return hashlib.sha256(blob).hexdigest()


def manifest_tail(gen: int) -> bytes:
    return struct.pack("<I", gen)
