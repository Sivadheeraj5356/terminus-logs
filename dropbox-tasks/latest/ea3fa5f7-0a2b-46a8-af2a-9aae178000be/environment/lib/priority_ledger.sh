#!/usr/bin/env bash
set -euo pipefail
python3 - "$1" "$2" <<'PY'
import json,sys
lat=json.loads(sys.argv[1])
rows=sorted(lat["acts"], key=lambda e:(e["o2"], -e["score"], e["cargo_id"]))
print(json.dumps({"schema_version":1,"tide_hash":lat["tide_hash"],"ranked":rows}))
PY
