"""Provenance hashing."""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path

from cfaxis.formats import Dataset


def operation_hash(op: str, paths: list[str]) -> str:
    hasher = hashlib.sha256()
    hasher.update(op.encode())
    for p in paths:
        hasher.update(p.encode())
        try:
            hasher.update(Path(p).read_bytes())
        except OSError:
            pass
    hasher.update(struct.pack("<Q", 0))
    return hasher.hexdigest()


def dataset_provenance(ds: Dataset) -> str:
    hasher = hashlib.sha256()
    hasher.update(ds.header.calendar.encode())
    hasher.update(ds.header.units.encode())
    hasher.update(struct.pack("<Q", ds.payload_len()))
    return hasher.hexdigest()
