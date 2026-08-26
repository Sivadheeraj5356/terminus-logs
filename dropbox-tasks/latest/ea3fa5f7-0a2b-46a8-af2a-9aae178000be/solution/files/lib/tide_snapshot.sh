#!/usr/bin/env bash
set -euo pipefail
python3 - "$1" "$2" <<'PY'
import hashlib,json,sys
d=json.loads(sys.argv[1]); mh=sys.argv[2]; hab=d["habitat"]; acts=[]
for c in d["cargo"]:
    start=c["dock_min"]+c["tide_ms"]/60000; dur=c["base_min"]*c["wave_m"]
    score=c["priority"]-c["wave_m"]*2-abs(c["tide_ms"])/60000
    nr=c.get("needs_rov") or c["lane"]!=hab["primary_lane"]
    acts.append({"cargo_id":c["cargo_id"],"dock_min":c["dock_min"],"tide_ms":c["tide_ms"],
      "berth_start":round(start,6),"transfer_min":round(dur,6),"berth_end":round(start+dur,6),
      "psi":c["psi"],"wave_m":c["wave_m"],"score":round(score,6),"lane":c["lane"],"needs_rov":nr,
      "m3":c["m3"],"cold":c["cold"],"o2":c["o2"]})
band=hab.get("berth_clock_band")
if band:
    for a in acts:
        bs=min(max(a["berth_start"],band["min"]),band["max"])
        a["berth_start"]=round(bs,6)
        a["berth_end"]=round(a["berth_start"]+a["transfer_min"],6)
body={"schema_version":1,"mission_hash":mh,"acts":acts}
body["tide_hash"]=hashlib.sha256(json.dumps({k:body[k] for k in body if k!="tide_hash"},separators=(",",":"),sort_keys=True).encode()).hexdigest()
print(json.dumps(body))
PY
