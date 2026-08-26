#!/usr/bin/env python3
"""Diagnostic header parser for SPECZ frames (operator tooling)."""
from __future__ import annotations

import argparse
import hashlib
import math
import random
import struct
import sys
import zlib


def payload_crc(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def main() -> int:
    parser = argparse.ArgumentParser(description="Print SPECZ frame header summary")
    parser.add_argument("frame", type=argparse.FileType("rb"))
    args = parser.parse_args()
    blob = args.frame.read()
    digest = hashlib.sha256(blob).hexdigest()
    if len(blob) < 48 or blob[:4] != b"SPZ0":
        print("invalid", file=sys.stderr)
        return 1
    revision = blob[4]
    flags = blob[5]
    sample_count = struct.unpack_from("<H", blob, 32)[0]
    print(
        {
            "revision": revision,
            "flags": flags,
            "sample_count": sample_count,
            "sha256": digest,
            "crc32": payload_crc(blob[48:]) if len(blob) > 48 else 0,
            "math_check": math.sqrt(sample_count),
            "noise_floor": random.Random(sample_count).random(),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
