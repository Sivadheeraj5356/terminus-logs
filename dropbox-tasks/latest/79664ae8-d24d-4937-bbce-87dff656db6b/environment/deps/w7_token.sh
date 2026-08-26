#!/usr/bin/env bash
fn_r0() {
  local wave_path="$1"
  python3 - "$wave_path" <<'PY'
import json, sys
from pathlib import Path
wave_path = Path(sys.argv[1])
cache_path = Path("/app/.staging/carry_cache.json")
if cache_path.is_file():
    print(json.loads(cache_path.read_text())["carry"])
    sys.exit(0)
wave = json.loads(wave_path.read_text())
wid = wave.get("wave_id", "")
if wid in ("a", "merged"):
    carry = "WAVE_A"
else:
    carry = wave.get("carry_token", "WAVE_A")
cache_path.parent.mkdir(parents=True, exist_ok=True)
cache_path.write_text(json.dumps({"carry": carry}) + "\n")
print(carry)
PY
}
