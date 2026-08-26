#!/bin/bash
set -uo pipefail
cd /app 2>/dev/null || true
mkdir -p /logs/verifier
/opt/verifier/bin/python -m pytest --ctrf /logs/verifier/ctrf.json "${TEST_DIR:-/tests}/test_m1.py" -rA
if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
