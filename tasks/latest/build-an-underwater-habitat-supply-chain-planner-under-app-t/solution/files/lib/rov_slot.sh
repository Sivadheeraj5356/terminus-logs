#!/usr/bin/env bash
set -euo pipefail
python3 - "$1" "$2" <<'PY'
import hashlib,json,sys
lat=json.loads(sys.argv[1]); hab=json.loads(sys.argv[2])
lead=hab["rov_lead_min"]; turn=hab["rov_turn_min"]; bays=hab["rov_bays"]
offline=set(hab.get("rov_bays_offline") or [])
eligible=[i for i in range(bays) if (i+1) not in offline]
free=[0.0]*bays; out=[]
for a in sorted(lat["acts"], key=lambda e:(e["berth_start"],e["cargo_id"])):
    if not a["needs_rov"]: continue
    need=a["berth_start"]-lead; pick=min(eligible, key=lambda i:(max(free[i],need),i))
    s=max(free[pick],need); e=a["berth_start"]; free[pick]=e+turn
    out.append({"cargo_id":a["cargo_id"],"rov_id":f"R{pick+1}","start":round(s,6),"end":round(e,6)})
body={"schema_version":1,"tide_hash":lat["tide_hash"],"slots":out}
body["rov_hash"]=hashlib.sha256(json.dumps(body,separators=(",",":"),sort_keys=True).encode()).hexdigest()
print(json.dumps(body))
PY
