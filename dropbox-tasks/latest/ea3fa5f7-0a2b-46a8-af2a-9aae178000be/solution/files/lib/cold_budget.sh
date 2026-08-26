#!/usr/bin/env bash
set -euo pipefail
python3 - "$1" "$2" <<'PY'
import hashlib,json,sys
stg=json.loads(sys.argv[1]); hab=json.loads(sys.argv[2])
cap=hab["cold_cap_m3"]
# cold m3 from assignment cargo flagged cold in ranked order metadata
cold_vol=0.0
for row in stg["assignments"]:
    if row.get("cold"): cold_vol+=row.get("m3",0.0)
stg["cold_m3_used"]=round(cold_vol,6)
stg["cold_cap_ok"]=cold_vol<=cap+1e-9
if not stg["cold_cap_ok"]: stg["feasible"]=False
stg["staging_hash"]=hashlib.sha256(json.dumps({k:stg[k] for k in stg if k!="staging_hash"},separators=(",",":"),sort_keys=True).encode()).hexdigest()
print(json.dumps(stg))
PY
