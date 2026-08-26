#!/usr/bin/env bash
set -euo pipefail
python3 - "$1" <<'PY'
import hashlib,json,sys
d=json.loads(sys.argv[1]); h=d["habitat"]
body={"cargo":d["cargo"],"habitat":{k:h[k] for k in sorted(h) if k!="schema_version"}}
print(hashlib.sha256(json.dumps(body,separators=(",",":"),sort_keys=True).encode()).hexdigest())
PY
