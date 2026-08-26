#!/usr/bin/env bash
set -euo pipefail
python3 - "$1" "$2" <<'PY'
import hashlib,json,sys
stg=json.loads(sys.argv[1]); hab=json.loads(sys.argv[2])
pad=float(hab.get("handoff_pad_min") or 0)
by_berth={}
for row in stg["assignments"]:
    by_berth.setdefault(row["berth_id"], []).append(dict(row))
windows=[]
for bid, rows in by_berth.items():
    rows.sort(key=lambda e:(e["start"], e["cargo_id"]))
    for i, row in enumerate(rows):
        start=row["start"]; end=row["end"]; handoff=False
        if i>0 and row.get("gap_used") and pad:
            dur=end-start
            start=round(start+pad,6)
            end=round(start+dur,6)
            handoff=True
        windows.append({
            "cargo_id":row["cargo_id"],"berth_id":bid,"seq":0,
            "start":round(start,6),"end":round(end,6),"handoff":handoff,
        })
windows.sort(key=lambda e:(e["start"], e["cargo_id"]))
for i,w in enumerate(windows,1):
    w["seq"]=i
body={"schema_version":1,"tide_hash":stg["tide_hash"],"staging_hash":stg["staging_hash"],"windows":windows}
body["cert_hash"]=hashlib.sha256(json.dumps({k:body[k] for k in body if k!="cert_hash"},separators=(",",":"),sort_keys=True).encode()).hexdigest()
print(json.dumps(body))
PY
