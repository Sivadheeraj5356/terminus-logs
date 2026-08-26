"""Resample result cache."""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path

from cfaxis.formats import Dataset, read_ccf, write_ccf
from cfaxis.formats.io import FreqArg


def cache_key(ds: Dataset, freq: FreqArg) -> str:
    hasher = hashlib.sha256()
    freq_s = {FreqArg.MON: "mon", FreqArg.SEA: "sea", FreqArg.ANN: "ann"}[freq]
    hasher.update(freq_s.encode())
    hasher.update(ds.time_axis.calendar.as_str().encode())
    hasher.update(ds.time_axis.units.echo().encode())
    hasher.update(struct.pack("<q", ds.time_axis.start_unix()))
    hasher.update(struct.pack("<q", ds.time_axis.end_unix()))
    for v in ds.variables:
        hasher.update(v.name.encode())
        hasher.update(struct.pack("<Q", len(v.bytes)))
        payload = hashlib.sha256(v.bytes).digest()
        hasher.update(payload)
    return hasher.hexdigest()


def load_cached(cache_dir: Path, key: str) -> Dataset | None:
    path = cache_dir / f"{key}.ccf"
    if not path.exists():
        return None
    return read_ccf(path)


def store_cached(cache_dir: Path, key: str, ds: Dataset) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{key}.ccf"
    write_ccf(path, ds)
