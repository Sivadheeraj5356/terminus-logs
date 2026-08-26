#!/usr/bin/env bash
set -uo pipefail

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

BINARY=/workspace/tribunal-game

if [ ! -f "${BINARY}" ]; then
    (cd /workspace && go build -o "${BINARY}" . 2>&1) || {
        echo "[test.sh] Build failed" >&2
        echo 0 > /logs/verifier/reward.txt
        exit 0
    }
fi

pytest "$(dirname "$0")/test_outputs.py" -v -rA --tb=short \
    --ctrf /logs/verifier/ctrf.json
RESULT=$?

if [ $RESULT -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
