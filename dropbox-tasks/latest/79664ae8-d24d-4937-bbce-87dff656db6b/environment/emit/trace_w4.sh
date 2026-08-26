#!/usr/bin/env bash
source /app/environment/emit/metric_k.sh

fn_r4() {
  local manifest_in="$1"
  local journal_in="$2"
  local loader_out="$3"
  python3 - "$manifest_in" "$journal_in" "$loader_out" <<'PY'
import json, subprocess, sys
from pathlib import Path
manifest = json.loads(Path(sys.argv[1]).read_text())
out_path = Path(sys.argv[3])
env = Path("/app/environment")
profiles = json.loads((env / "data/profiles.json").read_text())
profile = manifest.get("profile", "")
weights_path = env / profiles["profiles"][profile]["weights"]
weights = {}
for line in weights_path.read_text().splitlines():
    parts = line.strip().split("\t")
    if len(parts) == 2:
        weights[parts[0]] = int(parts[1])
read_order = sorted(weights.keys())
proc = subprocess.run(
    ["bash", "-c", f'source /app/environment/emit/metric_k.sh && fn_compute_trace_rows "{sys.argv[1]}" "{profile}"'],
    check=True,
    capture_output=True,
    text=True,
)
rows = json.loads(proc.stdout)
payload = {
    "profile": profile,
    "status_token": "CLEAN",
    "read_order": read_order,
    "rows": rows,
}
Path(out_path).write_text(json.dumps(payload, indent=2) + "\n")
PY
}
