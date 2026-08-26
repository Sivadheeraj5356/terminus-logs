#!/usr/bin/env bash
# Verifier entry point. The pytest suite builds the agent crate, drives its CLI,
# and compares the run database against an independent numpy reference engine.
set -uo pipefail

TESTDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="/usr/local/cargo/bin:${PATH}"
mkdir -p /app/out /logs/verifier

python3 -m pytest "${TESTDIR}/test_outputs.py" -v -rA
rc=$?
if [ "$rc" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
