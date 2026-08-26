#!/usr/bin/env bash
fn_compute_trace_rows() {
  local manifest_in="$1"
  local profile="$2"
  python3 - "$manifest_in" "$profile" <<'PY'
import json, sys
from pathlib import Path
manifest = json.loads(Path(sys.argv[1]).read_text())
profile = sys.argv[2]
env = Path("/app/environment")
profiles = json.loads((env / "data/profiles.json").read_text())
required = set(profiles["profiles"][profile]["required"])
manifest_obj_names = [o["name"] for o in manifest.get("objects", [])]
weights_path = env / profiles["profiles"][profile]["weights"]
weights = {}
for line in weights_path.read_text().splitlines():
    parts = line.strip().split("\t")
    if len(parts) == 2:
        weights[parts[0]] = int(parts[1])
read_order = sorted(weights.keys())
hook_state_path = Path("/app/.staging/hook_state.json")
commits = {}
if hook_state_path.is_file():
    for row in json.loads(hook_state_path.read_text()).get("commits", []):
        if row.get("committed"):
            commits[row["lane"]] = True
journal_union = set()
journal_path = Path("/app/.staging/phase_journal.json")
if journal_path.is_file():
    for seg in json.loads(journal_path.read_text()).get("segments", []):
        journal_union.update(seg.get("objects", []))
# warm inherit looks at blob lane; cold still pins object-lane commits
inherit_lane = "B" if profile == "warm" else "O"
rows = []
for name in read_order:
    lane = next((o["lane"] for o in manifest["objects"] if o["name"] == name), "O")
    if name not in manifest_obj_names:
        metric = 0
    elif name not in journal_union:
        metric = 0
    elif name in required and commits.get(lane, False):
        metric = 1
    elif name in required and lane == "O" and commits.get(inherit_lane, False):
        metric = 1
    else:
        metric = 0
    rows.append({"object": name, "avail_metric": metric, "lane": lane})
rows.sort(key=lambda r: r["object"])
print(json.dumps(rows))
PY
}
