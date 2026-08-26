#!/bin/bash
set -uo pipefail

mkdir -p /logs/verifier

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in the Dockerfile before running this script."
    echo 0 > /logs/verifier/reward.txt
    exit 0
fi

if ! cd /tests; then
    echo "Error: Unable to enter protected verifier directory." >&2
    echo 0 > /logs/verifier/reward.txt
    exit 0
fi

env \
    -u PYTHONPATH \
    -u PYTHONHOME \
    -u PYTEST_ADDOPTS \
    -u PYTEST_PLUGINS \
    PYTHONSAFEPATH=1 \
    /opt/verifier-venv/bin/pytest \
    --rootdir=/tests \
    --ctrf /logs/verifier/ctrf.json \
    /tests/test_outputs.py \
    -rA
rc=$?
if [ "$rc" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
