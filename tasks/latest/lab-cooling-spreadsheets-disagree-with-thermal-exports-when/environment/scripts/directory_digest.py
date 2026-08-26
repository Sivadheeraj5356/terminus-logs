"""Documented directory digest helper for calibration_report input_digest."""

from __future__ import annotations

import hashlib
from pathlib import Path

__all__ = ["directory_digest"]


def directory_digest(root: Path) -> str:
    files = sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())
    h = hashlib.sha256()
    for rel in files:
        h.update(rel.encode())
        h.update(b"\n")
        h.update((root / rel).read_bytes())
        h.update(b"\n")
    return h.hexdigest()
