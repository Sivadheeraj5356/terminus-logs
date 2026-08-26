#!/bin/bash
set -uo pipefail

mkdir -p /logs/verifier/ctrf
echo 0 > /logs/verifier/reward.txt

CTRF=/logs/verifier/ctrf/ctrf.json
CTRF_SKELETON='{"results":{"tool":{"name":"pytest"},"summary":{"tests":0,"passed":0,"failed":0,"skipped":0,"pending":0,"other":0},"tests":[]}}'

# The failure analyzer reads this canonical path. Create a fallback before any
# verifier work so even an interrupted run has a machine-readable report.
printf '%s\n' "$CTRF_SKELETON" > "$CTRF"
ensure_ctrf() {
    if [ ! -f "$CTRF" ]; then
        printf '%s\n' "$CTRF_SKELETON" > "$CTRF"
    fi
}
trap ensure_ctrf EXIT

/opt/verifier-venv/bin/python -m pytest \
    --ctrf "$CTRF" \
    -rA -vv --tb=short \
    /tests/test_outputs.py \
    2>&1 | tee /logs/verifier/pytest.log
rc=$?

if [ "$rc" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
