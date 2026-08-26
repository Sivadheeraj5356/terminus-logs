#!/bin/bash
set -uo pipefail

# Tests run from the isolated verifier venv (/opt/verifier-venv), built at image
# time. Runtime is offline; this script installs nothing and reaches no network.

mkdir -p /logs/verifier
TEST_DIR="${TEST_DIR:-/tests}"

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile."
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

# Regenerate the audit artifacts from the agent's current policy so a
# hand-written decisions file cannot pass.
rm -f /app/out/decisions.json /app/out/policy_input.json /app/out/hash_report.json
bash /app/bin/ledger-audit || true

/opt/verifier-venv/bin/python -m pytest -o cache_dir=/tmp/pytest_cache \
    --ctrf /logs/verifier/ctrf.json "$TEST_DIR/test_fixtures.py" \
    "$TEST_DIR/test_decisions.py" "$TEST_DIR/test_generalization.py" -rA
if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
