#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

cd "$ROOT"
make test
make build

if [[ ! -x "$ROOT/bin/beacon-drift" ]]; then
  echo "expected build to create bin/beacon-drift" >&2
  exit 1
fi

OUT_OK="$TMP/valid-result.json"
OUT_BAD="$TMP/invalid-result.json"
(
  cd "$TMP"
  "$ROOT/bin/beacon-drift" --profile north-pier --input "$ROOT/fixtures/packet_valid.json" --output "$OUT_OK"
  "$ROOT/bin/beacon-drift" --profile north-pier --input "$ROOT/fixtures/packet_invalid.json" --output "$OUT_BAD"
)

python3 - "$OUT_OK" "$OUT_BAD" <<'PY'
import json
import sys
ok_path, bad_path = sys.argv[1:]
with open(ok_path, encoding="utf-8") as f:
    ok = json.load(f)
with open(bad_path, encoding="utf-8") as f:
    bad = json.load(f)
assert ok["beacon_id"] == "NB-104", ok
assert ok["profile"] == "north-pier", ok
assert ok["accepted"] is True, ok
assert ok["severity"] == "clear", ok
assert ok["reasons"] == [], ok
assert bad["beacon_id"] == "NB-105", bad
assert bad["accepted"] is False, bad
assert bad["severity"] == "hold", bad
assert bad["reasons"] == sorted(bad["reasons"]), bad
for reason in ["battery_below_policy", "drift_limit_exceeded", "zone_not_allowed"]:
    assert reason in bad["reasons"], bad
PY

if find "$ROOT" \( -name .DS_Store -o -name node_modules -o -name vendor -o -name coverage.out -o -name __pycache__ \) | grep -q .; then
  echo "repository contains generated or forbidden files" >&2
  exit 1
fi

echo "smoke test passed"
