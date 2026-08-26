#!/bin/bash

# Verifier dependencies are installed in environment/Dockerfile.
# Add task-specific verifier-only Python packages there, not here.

mkdir -p /logs/verifier

# Pre-write a default failing reward so a timeout or early crash (before the
# pytest exit code is evaluated) still leaves a reward file behind.
echo 0 > /logs/verifier/reward.txt

TEST_DIR="${TEST_DIR:-/tests}"

python -m pytest -o cache_dir=/tmp/pytest_cache \
  --ctrf /logs/verifier/ctrf.json "$TEST_DIR/test_outputs.py" -rA
RC=$?
if [ "$RC" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
