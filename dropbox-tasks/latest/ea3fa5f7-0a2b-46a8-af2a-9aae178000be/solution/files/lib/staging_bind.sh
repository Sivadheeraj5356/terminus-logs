#!/usr/bin/env bash
set -euo pipefail
python3 - "$1" "$2" "$3" "$4" "$5" <<'PY'
import hashlib,json,sys
stg=json.loads(sys.argv[1]); mh=sys.argv[2]; hab=json.loads(sys.argv[3]); rov=json.loads(sys.argv[4]); cert=json.loads(sys.argv[5])
berth_ids=sorted(b["berth_id"] for b in hab["berths"])
body={"schema_version":1,"mission_hash":mh,"tide_hash":stg["tide_hash"],"staging_hash":stg["staging_hash"],
      "cert_hash":cert["cert_hash"],
      "feasible":stg.get("feasible",False),"cold_cap_ok":stg.get("cold_cap_ok",False),"cold_m3_used":stg.get("cold_m3_used",0),
      "mission_label":hab["mission_label"],"rov_bays":hab["rov_bays"],"berth_ids":berth_ids,"rov_hash":rov["rov_hash"]}
body["bind_hash"]=hashlib.sha256(json.dumps(body,separators=(",",":"),sort_keys=True).encode()).hexdigest()
print(json.dumps(body))
PY
