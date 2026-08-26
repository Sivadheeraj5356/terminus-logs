#!/bin/bash
set -euo pipefail

cd /app

cp /solution/fixed-src/matrix.c /app/src/matrix.c
cp /solution/fixed-src/assignment.c /app/src/assignment.c
cp /solution/fixed-src/markdown.c /app/src/markdown.c
cp /solution/fixed-src/reconcile.c /app/src/reconcile.c
cp /solution/fixed-src/report.c /app/src/report.c
cp /solution/fixed-src/main.c /app/src/main.c

make -C /app clean
make -C /app

mkdir -p /app/reports
/app/scripts/start-instrument.sh

/app/bin/tofmass \
  --api http://127.0.0.1:8791 \
  --run-id shot-2025-0314 \
  --notes /app/docs/lab-notes \
  --schema /app/docs/report.schema.json \
  --out /app/reports/mz-axis-reconcile.json

python3 - <<'PY'
import hashlib, json, math
from pathlib import Path

rep = json.loads(Path("/app/reports/mz-axis-reconcile.json").read_text())
assert rep["schema_version"] == 2
assert rep["producer"] == "tofmass"
assert rep["run_id"] == "shot-2025-0314"
assert rep["axis"]["source"] == "robust_gls"
assert rep["summary"]["accepted"] == 4
assert rep["summary"]["outlier"] == 1
assert rep["summary"]["no_match"] == 1
schema = Path("/app/docs/report.schema.json").read_bytes()
assert rep["schema_digest"] == hashlib.sha256(schema).hexdigest()
assert len(rep["ledger_digest"]) == 64
print("oracle local checks ok", rep["ledger_digest"][:16])
PY

echo "oracle reconcile complete"
