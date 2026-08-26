#!/usr/bin/env bash
set -euo pipefail
SCRATCH=/app/environment/r43/.scratch
if [[ "${1:-}" == "--restore-from" ]]; then
  SRC=${2:?pin table}
  rm -rf "$SCRATCH"
  mkdir -p "$SCRATCH"
  python3 - <<PY
import json, pathlib, sys
text = pathlib.Path("$SRC").read_text()
sections = {}
cur = None
for line in text.splitlines():
    line=line.strip()
    if not line or line.startswith('#'):
        continue
    if line.startswith('[') and line.endswith(']'):
        cur=line[1:-1]
        sections[cur]={}
        continue
    if '=' in line and cur:
        k,v=line.split('=',1)
        k=k.strip(); v=v.strip()
        if v.startswith('['):
            items=[x.strip().strip('"') for x in v.strip('[]').split(',') if x.strip()]
            sections[cur][k]=items
        else:
            sections[cur][k]=v.strip('"')
hi=sections.get('e_hi', {"allow":[], "rev":[]})
pathlib.Path("$SCRATCH/cur.json").write_text(json.dumps(hi))
print("restored")
PY
  exit 0
fi
# Destructive clear of rotation scratch
rm -rf "$SCRATCH"
mkdir -p "$SCRATCH"
echo "scratch cleared"
