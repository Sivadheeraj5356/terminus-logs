#!/usr/bin/env bash
set -euo pipefail
source /app/environment/deps/probe_w0.sh
PROFILE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile) PROFILE="$2"; shift 2 ;;
    *) echo "usage: run_w5.sh --profile warm|cold" >&2; exit 2 ;;
  esac
done
[[ -n "$PROFILE" ]] || exit 2
mkdir -p /app/.staging
probe_host_only /app/.staging/probe_order.json
python3 - "$PROFILE" <<'PY'
import json, sys
from pathlib import Path
profile = sys.argv[1]
env = Path("/app/environment")
profiles = json.loads((env / "data/profiles.json").read_text())
weights_path = env / profiles["profiles"][profile]["weights"]
names = []
for line in weights_path.read_text().splitlines():
    parts = line.strip().split("\t")
    if len(parts) == 2:
        names.append(parts[0])
mode = "weight" if profile == "warm" else "name"
hint = {"mode": mode, "names": sorted(names), "profile": profile}
Path("/app/.staging/worker_hint.json").write_text(json.dumps(hint, indent=2) + "\n")
PY
