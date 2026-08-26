#!/bin/bash

# Verifier dependencies are installed in environment/Dockerfile.
# Add task-specific verifier-only Python packages there, not here.

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
trap '[ -f /logs/verifier/reward.txt ] || echo 0 > /logs/verifier/reward.txt' EXIT

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile before running this script."
    exit 1
fi

# PYTHONNOUSERSITE/PYTHONSAFEPATH stop collection from picking up a
# sitecustomize.py, .pth file, or shadow module left under /app during the
# solve; -c/--rootdir/--noconftest pin config and conftest discovery to
# /tests instead of letting pytest walk up toward /app or /.
PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 python3 -m pytest -o cache_dir=/tmp/pytest_cache \
  -c /tests/pytest.ini --rootdir=/tests --noconftest \
  --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA

if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
