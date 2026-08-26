#!/bin/bash
mkdir -p /logs/verifier
# Initialize reward to 0 so any early-exit path still leaves a valid reward.
echo 0 > /logs/verifier/reward.txt
if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile before running this script."
    exit 1
fi
# Rebuild from the agent's corrected source so the verifier tests the actual
# fix and not the binary that was built into the image before the agent ran.
# If the build fails, the stale binary remains and the tests fail (reward 0).
( cd /app && cargo build --release --locked )
python3 -m pytest -o cache_dir=/tmp/pytest_cache \
  --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA
if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
