#!/bin/bash
set -uo pipefail

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set."
    exit 1
fi

TEST_DIR="${TEST_DIR:-/tests}"
chmod -R go-rwx "$TEST_DIR" 2>/dev/null || true
if ! cd "$TEST_DIR"; then
    echo "Error: verifier test directory is unavailable." >&2
    exit 0
fi

env -i \
    HOME=/tmp \
    PATH=/opt/verifier/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    PYTHONSAFEPATH=1 \
    TEST_DIR="$TEST_DIR" \
    /opt/verifier/bin/python -I -m pytest \
    -c /dev/null \
    --rootdir="$TEST_DIR" \
    -p no:cacheprovider \
    --ctrf /logs/verifier/ctrf.json \
    test_outputs.py -rA
if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
