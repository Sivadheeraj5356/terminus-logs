#!/usr/bin/env bash
set -euo pipefail
python3 - "$1" "$2" <<'PY'
import hashlib,json,sys
ledger=json.loads(sys.argv[1]); tide_hash=sys.argv[2]
entries=[{"cargo_id":r["cargo_id"],"o2":r["o2"]} for r in ledger["ranked"]]
body={"schema_version":1,"tide_hash":tide_hash,"entries":entries}
body["freeze_hash"]=hashlib.sha256(json.dumps({k:body[k] for k in ("schema_version","tide_hash","entries")},separators=(",",":"),sort_keys=True).encode()).hexdigest()
print(json.dumps(body))
PY
