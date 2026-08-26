#!/usr/bin/env bash
set -euo pipefail

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

if [ "$PWD" = "/" ]; then
  echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile."
  exit 1
fi
# conftest verifier_bootstrap runs rebuild-rollbackctl before pytest

set +e
/opt/verifier-venv/bin/python3 -m pytest \
  -rA \
  -o cache_dir=/tmp/pytest_cache \
  --ctrf /logs/verifier/ctrf.json \
  /tests/test_outputs.py \
  /tests/test_rollback_wave_contract.py \
  /tests/test_closure_partition_gates.py \
  /tests/test_truth_ledger_gates.py \
  /tests/test_egress_lane_gates.py \
  /tests/test_midpipe_chain_gates.py \
  /tests/test_witness_quorum_gates.py \
  /tests/test_topology_epoch_gates.py
rc=$?
if [ "$rc" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
