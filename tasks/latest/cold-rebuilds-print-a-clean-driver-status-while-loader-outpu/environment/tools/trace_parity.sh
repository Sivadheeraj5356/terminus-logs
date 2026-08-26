#!/usr/bin/env bash
source /app/environment/lib/stamp_k.sh

parity_read_order() {
  local profile="$1"
  local tbl="/app/environment/$(python3 - <<PY
import json
p=json.load(open("/app/environment/data/profiles.json"))
print(p["profiles"]["$profile"]["weights"])
PY
)"
  weight_order "$tbl"
}

index_bind_check() {
  local profile="$1"
  python3 - "$profile" <<'PY'
import json, sys
from pathlib import Path
profile = sys.argv[1]
env = Path("/app/environment")
profiles = json.loads((env / "data/profiles.json").read_text())
weights_path = env / profiles["profiles"][profile]["weights"]
weights = {}
for line in weights_path.read_text().splitlines():
    parts = line.strip().split("\t")
    if len(parts) == 2:
        weights[parts[0]] = int(parts[1])
wave = json.loads(Path("/app/.staging/active_wave.json").read_text())
names = sorted(o["name"] for o in wave["objects"])
expected = sorted(names, key=lambda n: (-weights[n], n))
host = json.loads(Path("/app/.staging/host_index.json").read_text())["order"]
chroot = json.loads(Path("/app/.staging/chroot_index.json").read_text())["order"]
if host != expected or chroot != expected:
    raise SystemExit(1)
print("ok")
PY
}

parity_avail() {
  local profile="$1"
  local journal="$2"
  local manifest="$3"
  python3 - "$profile" "$journal" "$manifest" <<'PY'
import json, sys
from pathlib import Path
profile, journal_path, manifest_path = sys.argv[1:4]
env = Path("/app/environment")
profiles = json.loads((env / "data/profiles.json").read_text())
required = set(profiles["profiles"][profile]["required"])
journal = json.loads(Path(journal_path).read_text())
manifest = json.loads(Path(manifest_path).read_text())
hook_state_path = Path("/app/.staging/hook_state.json")
commits = {}
if hook_state_path.is_file():
    for row in json.loads(hook_state_path.read_text()).get("commits", []):
        if row.get("committed"):
            commits[row["lane"]] = True
read_order = []
weights_path = env / profiles["profiles"][profile]["weights"]
weights = {}
for line in weights_path.read_text().splitlines():
    parts = line.strip().split("\t")
    if len(parts) == 2:
        weights[parts[0]] = int(parts[1])
read_order = sorted(weights.keys(), key=lambda n: (-weights[n], n))
rows = []
for name in read_order:
    lane = next((o["lane"] for o in manifest["objects"] if o["name"] == name), "O")
    metric = 1 if name in required and name in read_order and commits.get(lane, False) else (1 if name in required and name in read_order and lane == "O" and commits.get("B", False) else 0)
    if name not in [o["name"] for o in manifest["objects"]]:
        metric = 0
    rows.append({"object": name, "avail_metric": metric, "lane": lane})
print(json.dumps({"read_order": read_order, "rows": rows}))
PY
}
