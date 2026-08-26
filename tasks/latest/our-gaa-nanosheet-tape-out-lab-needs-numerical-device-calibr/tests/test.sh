#!/bin/bash

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

if [ "$PWD" = "/" ]; then
  echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile."
  exit 1
fi

set +e
TEST_DIR="${TEST_DIR:-/tests}"
cd /app

# Rebuild the submitted tb3 kernel from source (cargo build --release --locked
# -p tb3) under the strace trace guard so no build script can read the mounted
# reference tests. The guard exits non-zero on any protected-path read.
# Reward is already seeded to 0 above for any early exit.
bash "${TEST_DIR}/verifier-support/build_guard.sh" || exit 1

/opt/verifier-venv/bin/python3 -m pytest -o cache_dir=/tmp/pytest_cache \
  --ctrf /logs/verifier/ctrf.json "${TEST_DIR}/test_outputs.py" -rA

if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
