#!/bin/bash

export PATH="/opt/verifier-venv/bin:/usr/local/go/bin:${PATH}"

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

TEST_DIR="${TEST_DIR:-/tests}"

# Rebuild from /app without cd'ing away from the verifier tree.
if [ -f /app/go.mod ]; then
    go build -C /app -trimpath -o /app/bin/siggate ./cmd/siggate || {
        echo 0 > /logs/verifier/reward.txt
        exit 1
    }
fi

set +e
cd "${TEST_DIR}" || {
    echo 0 > /logs/verifier/reward.txt
    exit 1
}
/opt/verifier-venv/bin/python -m pytest -o cache_dir=/tmp/pytest_cache \
  test_outputs.py -rA
rc=$?

if [ "$rc" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
