#!/usr/bin/env bash
set -euo pipefail
APP_ROOT="${APP_ROOT:-/app}"
source "${APP_ROOT}/lib/common.sh"
python3 - <<'PY'
import hashlib,json
from pathlib import Path
APP=Path("/app")
tide=json.loads((APP/"state/tide-snapshot.json").read_text())
rov=json.loads((APP/"state/rov-index.json").read_text())
stg=json.loads((APP/"state/berth-staging.json").read_text())
cert=json.loads((APP/"state/transfer-cert.json").read_text())
bind=json.loads((APP/"state/export-bind.json").read_text())
man=json.loads((APP/"state/ingest-manifest.json").read_text())
freeze=json.loads((APP/"state/o2-priority-freeze.json").read_text())
if bind["bind_hash"]!=man.get("bind_hash","x"): raise SystemExit("bind mismatch")
if not stg.get("feasible"): raise SystemExit("infeasible")
if not stg.get("cold_cap_ok"): raise SystemExit("cold cap")
slots={s["cargo_id"]:s for s in rov["slots"]}
o2_by={e["cargo_id"]:e["o2"] for e in freeze["entries"]}
surge_ids={r["cargo_id"] for r in stg["assignments"] if r.get("surge")}
lines=[]
for row in cert["windows"]:
    slot=slots.get(row["cargo_id"])
    lines.append({"cargo_id":row["cargo_id"],"berth_id":row["berth_id"],"seq":row["seq"],
      "start":row["start"],"end":row["end"],"rov_id":slot["rov_id"] if slot else None,
      "surge":row["cargo_id"] in surge_ids,"o2":o2_by[row["cargo_id"]]})
plan={"schema_version":1,"mission_label":bind["mission_label"],"lines":lines,
      "tide_hash":tide["tide_hash"],"staging_hash":stg["staging_hash"]}
bind_s=json.dumps(plan,separators=(",",":"),sort_keys=True)
berth_load={bid:sum(1 for l in lines if l["berth_id"]==bid) for bid in bind["berth_ids"]}
report={"schema_version":1,"rov_bays":bind["rov_bays"],"cold_m3_used":stg["cold_m3_used"],
        "berth_load":berth_load,
        "fingerprint":hashlib.sha256(bind_s.encode()).hexdigest()}
(APP/"output").mkdir(parents=True,exist_ok=True)
(APP/"output/resupply-plan.json").write_text(json.dumps(plan,indent=2)+"\n")
(APP/"output/utilization-report.json").write_text(json.dumps(report,indent=2)+"\n")
PY
