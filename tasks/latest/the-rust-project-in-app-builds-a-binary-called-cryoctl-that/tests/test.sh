#!/bin/bash
set -uo pipefail

mkdir -p /logs/verifier

# Default the reward to 0 before any risky verifier work runs, so that if
# /app/build.sh (or anything after it) crashes the harness, reward.txt already
# holds a failing score rather than being absent. The final 1/0 is rewritten
# after pytest below.
echo 0 > /logs/verifier/reward.txt

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile before running this script."
    echo 0 > /logs/verifier/reward.txt
    exit 0
fi

# Rebuild the Rust binary from source so the verifier scores the agent's actual
# fix to src/main.rs, not whatever executable happens to sit at /app/cryoctl.
# A missing/broken build must fail the task, so guard the reward on it.
if ! /app/build.sh; then
    echo "Error: /app/build.sh failed; cannot verify against a freshly built binary."
    echo 0 > /logs/verifier/reward.txt
    exit 0
fi

python -m pytest --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA
rc=$?
if [ "$rc" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
