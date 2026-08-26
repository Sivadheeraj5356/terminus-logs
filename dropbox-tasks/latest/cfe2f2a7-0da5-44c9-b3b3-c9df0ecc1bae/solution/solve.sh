#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cp -a "$ROOT_DIR/oracle/." /app/environment/

cd /app/environment
go build -o /app/environment/bin/hopledger .

mkdir -p /app/output
/app/environment/bin/hopledger run \
  --manifest /app/environment/fixtures/manifest.json \
  --report /app/output/report.json \
  --digest /app/output/digest.txt \
  --audit /app/output/audit.jsonl

# Sanity-check resume equivalence on a generated manifest.
GEN=/tmp/hopledger-oracle-resume
rm -rf "$GEN"
python3 /tests/hop_expect.py --generate 241 "$GEN"
/app/environment/bin/hopledger run \
  --manifest "$GEN/manifest.json" \
  --report "$GEN/full.json" \
  --digest "$GEN/full.digest" \
  --audit "$GEN/full.audit.jsonl"
CKPT=$(python3 -c "
import json, subprocess
exp = json.loads(subprocess.check_output(['python3','/tests/hop_expect.py', '$GEN/manifest.json']))
for line in exp['audit'].splitlines():
    row = json.loads(line)
    if row['decision']=='checkpoint':
        print(row['reason']); break
")
/app/environment/bin/hopledger run \
  --manifest "$GEN/manifest.json" \
  --report "$GEN/resume.json" \
  --digest "$GEN/resume.digest" \
  --audit "$GEN/resume.audit.jsonl" \
  --resume-tag "$CKPT"
cmp -s "$GEN/full.json" "$GEN/resume.json"
cmp -s "$GEN/full.digest" "$GEN/resume.digest"
cmp -s "$GEN/full.audit.jsonl" "$GEN/resume.audit.jsonl"
