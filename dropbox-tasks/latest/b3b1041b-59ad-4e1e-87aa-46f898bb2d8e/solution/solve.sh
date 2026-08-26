#!/bin/bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p /app/output /app/output/stage /app/output/traces

VERIFY=(/app/environment/tools/k9_verify --matrix all
  --witness-out /app/output/replay_witness.json
  --spec-out /app/output/inferred_spec.json)

smoke_matrix() {
  rm -rf /app/environment/r43/.scratch
  mkdir -p /app/environment/r43/.scratch
  bash /app/environment/scripts/build_lab.sh
  "${VERIFY[@]}"
}

patch -d /app -p1 < "${ROOT_DIR}/patches/cfg_lane.rb.patch"
patch -d /app -p1 < "${ROOT_DIR}/patches/lane_cache.rb.patch"
smoke_matrix || true

patch -d /app -p1 < "${ROOT_DIR}/patches/emit_w.rb.patch"
smoke_matrix || true

patch -d /app -p1 < "${ROOT_DIR}/patches/rot_fold.rb.patch"
patch -d /app -p1 < "${ROOT_DIR}/patches/gate_p.rb.patch"
smoke_matrix

python3 - <<'PY'
import json
from pathlib import Path

wit = json.loads(Path("/app/output/replay_witness.json").read_text(encoding="utf-8"))
spec = json.loads(Path("/app/output/inferred_spec.json").read_text(encoding="utf-8"))
grids = wit.get("grids") or {}
need = {"pocket", "ridge", "slate", "marsh"}
if not need.issubset(grids):
    raise SystemExit(f"missing grids: {need - set(grids)}")

for g, profiles in grids.items():
    for pid, cell in profiles.items():
        if cell.get("meta_state") != "aligned":
            raise SystemExit(f"meta diverged {g}/{pid}")
        keys = cell.get("eff_keys") or []
        if "__p" in keys or "x_def" in keys:
            raise SystemExit(f"pollution keys in eff_keys {g}/{pid}")
        if not cell.get("cfg_fp"):
            raise SystemExit(f"missing cfg_fp {g}/{pid}")
        rows = cell.get("rows") or []
        if not any(r.get("plan") == "ok" and r.get("gate") == "pass" for r in rows):
            raise SystemExit(f"no accepted rows {g}/{pid}")
        for r in rows:
            if r.get("plan") == "ok" and pid == "pri_hi" and r.get("e_tag") != "e_hi":
                raise SystemExit(f"epoch tag mismatch {g}/{pid}")
            if r.get("plan") == "ok" and pid == "pri_lo" and r.get("e_tag") != "e_lo":
                raise SystemExit(f"epoch tag mismatch {g}/{pid}")

if spec.get("schema") != "k84-spec-v1":
    raise SystemExit("spec schema mismatch")
if len(spec.get("clauses") or []) != 3:
    raise SystemExit("spec clause count mismatch")
if spec.get("band_epoch") != {"pri_hi": "e_hi", "pri_lo": "e_lo"}:
    raise SystemExit("band_epoch mismatch")

kinds = {c.get("kind") for c in spec.get("clauses") or []}
if kinds != {"cfg_iso", "w_bind", "rev_iso"}:
    raise SystemExit(f"clause kinds mismatch: {kinds}")

print("oracle coordination ok grids=", len(grids))
PY
