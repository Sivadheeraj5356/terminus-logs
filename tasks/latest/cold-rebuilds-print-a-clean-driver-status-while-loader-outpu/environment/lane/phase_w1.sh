#!/usr/bin/env bash
fn_r2() {
  local wave_json="$1"
  local journal_out="$2"
  python3 - "$wave_json" "$journal_out" <<'PY'
import json, subprocess, sys
from pathlib import Path
wave_path = Path("/app/environment") / sys.argv[1]
out_path = Path(sys.argv[2])
wave = json.loads(wave_path.read_text())
env = Path("/app/environment")
hint_path = Path("/app/.staging/worker_hint.json")
profile = "cold"
if hint_path.is_file():
    profile = json.loads(hint_path.read_text()).get("profile", "cold")
profiles = json.loads((env / "data/profiles.json").read_text())
weights_path = env / profiles["profiles"][profile]["weights"]
order_proc = subprocess.run(
    [
        "bash",
        "-c",
        'source /app/environment/lib/stamp_k.sh && weight_order "$1"',
        "_",
        str(weights_path),
    ],
    check=True,
    capture_output=True,
    text=True,
)
rank = {name: idx for idx, name in enumerate(order_proc.stdout.splitlines()) if name}
segments = []
hook_gen = 1
blob_epoch = 0
lane_rank = {"O": 0, "B": 1}
lanes_present = sorted({o["lane"] for o in wave["objects"]}, key=lambda l: lane_rank[l])
for lane in lanes_present:
    objs = [o["name"] for o in wave["objects"] if o["lane"] == lane]
    objs = sorted(objs, key=lambda n: (rank.get(n, 10**9), n))
    if not objs:
        continue
    if lane == "B":
        blob_epoch += 1
    seg_hook_gen = blob_epoch if lane == "B" else hook_gen
    segments.append({
        "lane": lane,
        "epoch": len(segments) + 1,
        "blob_epoch": blob_epoch,
        "hook_gen": seg_hook_gen,
        "objects": objs,
    })
    hook_gen += 1
    if lane == "B":
        hook_gen = blob_epoch
Path(out_path).write_text(json.dumps({"segments": segments}, indent=2) + "\n")
PY
}
