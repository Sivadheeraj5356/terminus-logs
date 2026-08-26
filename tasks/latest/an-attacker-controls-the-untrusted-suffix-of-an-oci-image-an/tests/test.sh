#!/bin/bash
set -uo pipefail

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

chmod 0700 /tests 2>/dev/null || true
if [ "$(stat -c '%a' /tests)" != "700" ]; then
    echo "Error: verifier cases are not private."
    exit 1
fi

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR."
    exit 1
fi

/usr/local/bin/python3 /tests/compile_unprivileged.py \
    /app/layer_gate.c /tmp/oci-layer-gate-candidate
compile_rc=$?
if [ "$compile_rc" -ne 0 ]; then
    echo 0 > /logs/verifier/reward.txt
    exit 0
fi

/usr/local/bin/python3 /tests/run_unprivileged.py --prepare
prepare_rc=$?
if [ "$prepare_rc" -ne 0 ]; then
    echo 0 > /logs/verifier/reward.txt
    exit 0
fi

/usr/local/bin/python3 -m pytest -o cache_dir=/tmp/pytest_cache /tests/test_outputs.py -rA
rc=$?

if [ "$rc" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
