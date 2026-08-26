#!/usr/bin/env bash
set -euo pipefail
python3 - "$1" "$2" "$3" "$4" <<'PY'
import hashlib,json,sys
mh,bind, seq, out=sys.argv[1:5]
bind=json.loads(bind)
body={"schema_version":1,"mission_hash":mh,"bind_hash":bind["bind_hash"],"rov_hash":bind.get("rov_hash",""),
      "run_sequence":int(seq),"feasible":bind["feasible"],"cold_cap_ok":bind.get("cold_cap_ok",False)}
body["manifest_hash"]=hashlib.sha256(json.dumps({k:body[k] for k in body if k!="manifest_hash"},separators=(",",":"),sort_keys=True).encode()).hexdigest()
open(out,"w").write(json.dumps(body,indent=2)+"\n")
PY
