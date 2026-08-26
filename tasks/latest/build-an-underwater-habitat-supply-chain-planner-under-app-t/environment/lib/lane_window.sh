#!/usr/bin/env bash
set -euo pipefail
# Lane window stage for tide acts. See /app/docs/tide-offset-windows.md and /app/docs/lane-window-offset.md.
python3 - "$1" "$2" <<'PY'
import hashlib,json,sys
tide=json.loads(sys.argv[1]); hab=json.loads(sys.argv[2])
windows=hab.get("lane_window_min") or {}
band=hab.get("berth_clock_band")
acts=[]
for a in tide["acts"]:
    row=dict(a)
    off=windows.get(row["lane"],0)
    if off:
        row["berth_start"]=round(row["berth_start"]+off,6)
        row["berth_end"]=round(row["berth_start"]+row["transfer_min"],6)
    if band:
        bs=min(max(row["berth_start"],band["min"]),band["max"])
        row["berth_start"]=round(bs,6)
        row["berth_end"]=round(row["berth_start"]+row["transfer_min"],6)
    acts.append(row)
body={"schema_version":tide["schema_version"],"mission_hash":tide["mission_hash"],"acts":acts}
body["tide_hash"]=hashlib.sha256(json.dumps({k:body[k] for k in body if k!="tide_hash"},separators=(",",":"),sort_keys=True).encode()).hexdigest()
print(json.dumps(body))
PY
