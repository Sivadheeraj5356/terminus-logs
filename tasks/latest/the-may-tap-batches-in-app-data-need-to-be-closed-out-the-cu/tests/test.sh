#!/bin/bash
# Keep `-e` off so pytest failures still write /logs/verifier/reward.txt.
set -uo pipefail

if [ "$PWD" = "/" ]; then
  echo "Error: No working directory set. Please set a WORKDIR in the Dockerfile before running this script."
  mkdir -p /logs/verifier
  echo 0 > /logs/verifier/reward.txt
  exit 0
fi

mkdir -p /logs/verifier

rm -rf /app/output
mkdir -p /app/output

node /app/reconcile.js
script_rc=$?
if [ "$script_rc" -ne 0 ]; then
  echo 0 > /logs/verifier/reward.txt
  exit 0
fi

RECONCILE_ALREADY_RAN=1 \
python3 -m pytest -p no:cacheprovider /tests/test_outputs.py -rA
rc=$?

if [ "$rc" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
