#!/usr/bin/env bash
set -uo pipefail

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set."
    exit 1
fi

mkdir -p /logs/verifier

TEST_DIR="${TEST_DIR:-/tests}"

cd /app
if command -v cargo >/dev/null 2>&1; then
    timeout 180 cargo build --locked --quiet
    build_rc=$?
else
    echo "cargo is not available in PATH" >&2
    build_rc=127
fi

if [ $build_rc -eq 0 ]; then
    RESOLVER_BIN=/app/target/debug/prism-dependency-forge pytest \
      --ctrf /logs/verifier/ctrf.json \
      "$TEST_DIR/test_outputs.py" \
      -rA
else
    false
fi

test_rc=$?
if [ "$test_rc" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
