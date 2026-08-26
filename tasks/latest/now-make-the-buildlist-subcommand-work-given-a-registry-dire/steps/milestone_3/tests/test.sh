#!/bin/bash
# Milestone 3 verifier: enforce the stdlib only constraint, confirm the reference
# is not reachable from the app tree, cold compile the modverse sources, then run
# the milestone 3 pytest suite against the CLI.
set -uo pipefail

TEST_DIR="${TEST_DIR:-/tests}"
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

if [ "$(pwd)" != "/app" ]; then
    cd /app || { echo "FAIL: expected working directory /app is not available"; exit 1; }
fi

SRC=/app/app/src/main/scala

BAD_IMPORTS=$(grep -rhnE '^[[:space:]]*import[[:space:]]' "$SRC" 2>/dev/null \
    | grep -vE 'import[[:space:]]+(scala\.|java\.|javax\.|modverse\.|[A-Z])' || true)
if [ -n "$BAD_IMPORTS" ]; then
    echo "FAIL: source imports a non stdlib package:"
    echo "$BAD_IMPORTS"
    exit 1
fi

if grep -rnE 'scala\.sys\.process|ProcessBuilder|\.getRuntime\(\)\.exec' "$SRC" >/dev/null 2>&1; then
    echo "FAIL: source shells out or spawns a process"
    exit 1
fi

if find /app -name 'modref.py' 2>/dev/null | grep -q . ; then
    echo "FAIL: modref.py is present under /app"
    exit 1
fi

if ! bash /app/app/build.sh > /tmp/build.log 2>&1; then
    echo "modverse build failed:"
    cat /tmp/build.log
    exit 1
fi

/opt/test-env/bin/pytest \
    -o cache_dir=/tmp/pytest_cache \
    --ctrf /logs/verifier/ctrf.json \
    "$TEST_DIR/test_m3.py" -rA

if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
