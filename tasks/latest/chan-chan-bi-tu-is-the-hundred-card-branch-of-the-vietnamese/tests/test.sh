#!/bin/bash
set -uo pipefail

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

rm -f /tmp/chandeck_bin
if ! ( cd /app && CGO_ENABLED=0 go build -o /tmp/chandeck_bin ./cmd/chandeck ) 1>&2; then
    echo 0 > /logs/verifier/reward.txt
    exit 0
fi

TEST_DIR="${TEST_DIR:-/tests}"
cd "$TEST_DIR" || { echo "verifier could not enter $TEST_DIR" 1>&2; echo 0 > /logs/verifier/reward.txt; exit 0; }
if [ "$PWD" = "/" ]; then
    echo "refusing to run pytest from /" 1>&2
    echo 0 > /logs/verifier/reward.txt
    exit 0
fi
python3 -m pytest -p no:cacheprovider -x "$TEST_DIR/test_outputs.py" -v -rA

status=$?
if [ "$status" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
