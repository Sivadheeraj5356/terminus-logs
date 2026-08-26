#!/usr/bin/env python3
"""Materialize the 32-byte AES label DEK from the checked-in hex file."""
from pathlib import Path

keys = Path("/app/data/keys")
dek = keys / "label_dek.bin"
dek.write_bytes(bytes.fromhex((keys / "label_dek.hex").read_text().strip()))
if dek.stat().st_size != 32:
    raise SystemExit(f"expected 32-byte DEK, got {dek.stat().st_size}")
