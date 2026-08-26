"""Reference digest helper for hash_view.fprint (tag:rev:move)."""

from __future__ import annotations

import hashlib
import sys


def fprint(tag: str, rev: int, move: int) -> str:
    raw = f"{tag}:{rev}:{move}".encode()
    return hashlib.sha256(raw).hexdigest()[:16]


if __name__ == "__main__":
    print(fprint(sys.argv[1], int(sys.argv[2]), int(sys.argv[3])))
