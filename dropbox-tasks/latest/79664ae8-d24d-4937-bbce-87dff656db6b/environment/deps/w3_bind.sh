#!/usr/bin/env bash
source /app/environment/lib/stamp_k.sh
source /app/environment/deps/w7_token.sh

fn_r1() {
  local host_tbl="$1"
  local chroot_tbl="$2"
  local profile="$3"
  local manifest_out="$4"
  local wave_path="/app/.staging/active_wave.json"
  local carry
  carry="$(fn_r0 "$wave_path")"
  python3 - "$host_tbl" "$chroot_tbl" "$profile" "$manifest_out" "$carry" <<'PY'
import json, subprocess, sys
from pathlib import Path
host_tbl, chroot_tbl, profile, manifest_out, carry = sys.argv[1:6]
env = Path("/app/environment")
profiles = json.loads((env / "data/profiles.json").read_text())
weights_path = env / profiles["profiles"][profile]["weights"]
weights = {}
for line in weights_path.read_text().splitlines():
    parts = line.strip().split("\t")
    if len(parts) == 2:
        weights[parts[0]] = int(parts[1])
hint = {}
hint_path = Path("/app/.staging/worker_hint.json")
if hint_path.is_file():
    hint = json.loads(hint_path.read_text())
probe_path = Path("/app/.staging/probe_order.json")
if probe_path.is_file():
    hint = {"mode": "name", "names": sorted(o["name"] for o in json.loads(Path("/app/.staging/active_wave.json").read_text()).get("objects", []))}
wave = json.loads(Path("/app/.staging/active_wave.json").read_text())
wave_names = sorted(o["name"] for o in wave["objects"])
host_order = sorted(wave_names, key=lambda n: (-weights.get(n, 0), n))
chroot_order = sorted(wave_names)
if hint.get("mode") == "name":
    chroot_order = sorted(hint.get("names", wave_names))
Path(host_tbl).write_text(json.dumps({"order": host_order}) + "\n")
Path(chroot_tbl).write_text(json.dumps({"order": chroot_order}) + "\n")
obj_names = [o["name"] for o in wave["objects"]]
cmd = [
    "bash", "-c",
    'source /app/environment/lib/stamp_k.sh && stamp_digest "$1" "$2" "${@:3}"',
    "_",
    profile,
    carry,
    *obj_names,
]
stamp = subprocess.check_output(cmd, text=True).strip()
manifest = {"profile": profile, "stamp": stamp, "carry": carry, "objects": wave["objects"]}
Path(manifest_out).write_text(json.dumps(manifest, indent=2) + "\n")
PY
}
