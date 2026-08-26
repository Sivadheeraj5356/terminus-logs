#!/usr/bin/env python3
"""Reference ledger_digest helper matching the Go DigestHex reduction."""
from __future__ import annotations

import hashlib
import sys


def ledger_digest(facet_hex_values: list[str]) -> str:
    return hashlib.sha256(",".join(facet_hex_values).encode()).hexdigest()


def main() -> None:
    print(ledger_digest(sys.argv[1:]))


if __name__ == "__main__":
    main()
