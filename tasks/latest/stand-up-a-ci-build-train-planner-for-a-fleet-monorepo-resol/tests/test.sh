#!/bin/bash

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

if [ "$PWD" = "/" ]; then
  echo "Error: No working directory set." >&2
  exit 1
fi

export PATH="/usr/local/go/bin:/opt/verifier-venv/bin:${PATH}"
export CGO_ENABLED=0
export GOPROXY=off
export GOSUMDB=off

TEST_ROOT="${TEST_DIR:-/tests}"
mkdir -p /opt/verifier-fixtures/state /opt/verifier-fixtures/fixtures
if [ -f "$TEST_ROOT/fixtures/hidden-release.pin" ]; then
  cp "$TEST_ROOT/fixtures/hidden-release.pin" /opt/verifier-fixtures/fixtures/
fi

cd /app || { echo "Error: /app not found." >&2; exit 1; }

if [ -d /app/cmd/fleetd ]; then
  go build -o /app/bin/fleetd ./cmd/fleetd
fi

/opt/verifier-venv/bin/python -m pytest -o cache_dir=/tmp/pytest_cache \
  --ctrf /logs/verifier/ctrf.json "$TEST_ROOT/test_outputs.py" -rA

if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
