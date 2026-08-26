#!/usr/bin/env bash
set -euo pipefail
ROOT=/app/environment
mkdir -p /app/output /app/output/stage /app/output/traces
mkdir -p "$ROOT/r43/.scratch"
# Drop lane bind cache on rebuild so overlay changes are re-evaluated.
rm -rf "$ROOT/r43/.scratch/lane"
# Seed active scratch (cur) from e_hi — mirrors production active pin cache.
python3 - <<'PY'
import json, pathlib, re
text = pathlib.Path("/app/environment/data/p39/pin_table.toml").read_text()
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
pathlib.Path("/app/environment/r43/.scratch").mkdir(parents=True, exist_ok=True)
pathlib.Path("/app/environment/r43/.scratch/cur.json").write_text(json.dumps(hi))
PY
# Ensure CLI shim exists when running on a tree that still has the package dir name.
if [[ -d "$ROOT/tools/k9_verify" && -f "$ROOT/tools/k9_verify/main.rb" ]]; then
  mv "$ROOT/tools/k9_verify" "$ROOT/tools/k9v"
  printf '%s\n' '#!/usr/bin/env bash' 'exec ruby /app/environment/tools/k9v/main.rb "$@"' > "$ROOT/tools/k9_verify"
  chmod +x "$ROOT/tools/k9_verify"
fi
if [[ -f "$ROOT/tools/k9_verify" ]]; then
  chmod +x "$ROOT/tools/k9_verify"
fi
chmod +x "$ROOT/scripts/run_grid.sh" "$ROOT/migrations/rst9.sh" || true
echo "lab build ok"
