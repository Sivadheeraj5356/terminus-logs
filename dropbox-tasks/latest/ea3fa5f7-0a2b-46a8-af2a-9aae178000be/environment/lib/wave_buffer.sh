#!/usr/bin/env bash
set -euo pipefail
# Wave buffer stage for tide acts. See /app/docs/wave-buffer.md.
python3 - "$1" "$2" <<'PY'
import hashlib,json,sys
tide=json.loads(sys.argv[1]); hab=json.loads(sys.argv[2])
thresh=hab.get("wave_buffer_threshold"); buf=hab.get("wave_buffer_min",0)
acts=[]
for a in tide["acts"]:
    row=dict(a)
    if thresh is not None and row["wave_m"]>thresh:
        row["transfer_min"]=round(row["transfer_min"]+buf,6)
        row["berth_end"]=round(row["berth_start"]+row["transfer_min"],6)
    acts.append(row)
body={"schema_version":tide["schema_version"],"mission_hash":tide["mission_hash"],"acts":acts}
body["tide_hash"]=hashlib.sha256(json.dumps({k:body[k] for k in body if k!="tide_hash"},separators=(",",":"),sort_keys=True).encode()).hexdigest()
print(json.dumps(body))
PY
