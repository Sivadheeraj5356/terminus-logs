#!/usr/bin/env bash
set -euo pipefail

export PATH="/usr/local/go/bin:/opt/verifier-venv/bin:/app/environment/bin:${PATH}"

log() { printf '[solve] %s\n' "$1"; }

cd /solution
patch -d /app/environment -p1 --batch < oracle.patch
cd /app/environment
./scripts/build_all.sh
npm run certify -- \
  --journal /app/environment/data/assay_journal.jsonl \
  --config /app/environment/data/assay_policy.json \
  --output /app/output/compliance_attestation_package.json \
  --cache-dir /app/cache/qpcr

log "sanity-check output contract"
python3 <<'PY'
import json
from pathlib import Path

data = json.loads(Path("/app/output/compliance_attestation_package.json").read_text(encoding="utf-8"))
assert data["schema"] == "qpcr-attestation-v2"
assert data["summary"]["assays_total"] == len(data["assays"])
assert data["summary"]["trace_total"] == len(data["trace"])
assert all(len(row["witness"]) == 64 for row in data["assays"])
PY

log "done"
