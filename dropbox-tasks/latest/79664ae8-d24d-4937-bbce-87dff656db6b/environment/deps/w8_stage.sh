#!/usr/bin/env bash
fn_wave_stage() {
  local wave_rel="$1"
  local merge_tier="$2"
  python3 - "$wave_rel" "$merge_tier" <<'PY'
import json, sys
from pathlib import Path
env = Path("/app/environment")
wave_rel, merge_tier = sys.argv[1], int(sys.argv[2])
wave_a = json.loads((env / "bundles/waves/wave_a.json").read_text())
if merge_tier == 0:
    Path("/app/.staging/active_wave.json").write_text(json.dumps(wave_a, indent=2) + "\n")
elif merge_tier == 1:
    wave_b = json.loads((env / "bundles/waves/wave_b.json").read_text())
    objs = {o["name"]: o for o in wave_a["objects"]}
    for o in wave_b["objects"]:
        objs[o["name"]] = o
    carry = wave_a.get("carry_token", "WAVE_A")
    merged = {"wave_id": "merged", "carry_token": carry, "objects": list(objs.values())}
    Path("/app/.staging/active_wave.json").write_text(json.dumps(merged, indent=2) + "\n")
elif merge_tier == 2:
    wave_b = json.loads((env / "bundles/waves/wave_b.json").read_text())
    wave_c = json.loads((env / "bundles/waves/wave_c.json").read_text())
    objs = {o["name"]: o for o in wave_a["objects"]}
    for o in wave_c["objects"]:
        objs[o["name"]] = o
    carry = wave_b.get("carry_token", "WAVE_B")
    merged = {"wave_id": "merged_t2", "carry_token": carry, "objects": list(objs.values())}
    Path("/app/.staging/active_wave.json").write_text(json.dumps(merged, indent=2) + "\n")
else:
    raise SystemExit(f"unsupported merge tier {merge_tier}")
PY
}
