"""Offline carry seed presence guard (not a graded digest reference)."""

from __future__ import annotations

import hashlib
from pathlib import Path

_SEED = Path(__file__).resolve().parents[1] / "fixtures" / "seed" / "cp_seed.bin"


def seed_fingerprint() -> str:
    data = _SEED.read_bytes()
    if not data:
        raise ValueError("empty carry seed")
    return hashlib.sha256(data).hexdigest()[:8]


if __name__ == "__main__":
    print(seed_fingerprint())
