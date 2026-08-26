#!/usr/bin/env python3
"""Tiny helper that mirrors the SHA-256 hex digests used for snapshot
attestation so operators can recompute chronicle and session-state digests
from the command line without starting the Go service.
"""

from __future__ import annotations

import hashlib
import sys


def hex_digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: sha256_hex.py <path>", file=sys.stderr)
        return 2
    path = argv[1]
    with open(path, "rb") as handle:
        print(hex_digest(handle.read()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
