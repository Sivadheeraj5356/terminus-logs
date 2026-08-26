#!/usr/bin/env bash
set -euo pipefail

ENV_ROOT=${1:-/app/environment}
IDL_DIR="$ENV_ROOT/idl"

python3 - "$IDL_DIR" <<'PY'
import sys
from pathlib import Path

idl = Path(sys.argv[1])
state = 1469598103934665603
prime = 1099511628211


def mix(data: bytes) -> None:
    global state
    for byte in data:
        state ^= byte
        state = (state * prime) & 0xFFFFFFFFFFFFFFFF


def mix_text(text: str) -> None:
    mix(text.encode("utf-8"))


pack = idl / "pack.order"

order = [
    line.strip()
    for line in pack.read_text().splitlines()
    if line.strip() and not line.strip().startswith("#")
]
for fragment in order:
    mix_text(fragment)
    mix((idl / "fragments" / fragment).read_bytes())

mix_text("compat")
mix((idl / "compat" / "legacy_slots.tsv").read_bytes())
mix_text("provenance")
mix((idl / "provenance.manifest").read_bytes())

print(f"{state:016x}")
PY
