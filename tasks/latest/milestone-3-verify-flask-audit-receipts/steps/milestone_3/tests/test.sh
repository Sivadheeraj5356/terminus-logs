#!/bin/bash
# Verifier dependencies are installed in environment/Dockerfile.
# Write a default reward of 0 BEFORE any early guard so that every exit path
# (including the no-working-directory guard below) leaves a reward on disk.
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set." >&2
    exit 1
fi
python -m pytest -o cache_dir=/tmp/pytest_cache --ctrf /logs/verifier/ctrf.json /tests/test_m3.py -rA
rc=$?
if [ $rc -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
