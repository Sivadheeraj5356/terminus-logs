#!/bin/bash
export PATH="/usr/local/go/bin:/opt/verifier-venv/bin:${PATH}"

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

if [ "$PWD" = "/" ]; then
  echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile."
  exit 1
fi

set +e

cd /app
go build -mod=vendor -o /app/bin/labyrinth-oracle ./cmd/labyrinth-oracle || exit 1

/opt/verifier-venv/bin/python -m pytest -o cache_dir=/tmp/pytest_cache \
  --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py \
  /tests/test_oracle_http.py \
  /tests/test_hint_contract.py \
  /tests/test_probe_stage.py \
  /tests/test_attest_gates.py \
  /tests/test_hidden_worlds.py \
  /tests/test_route_abort.py -rA

rc=$?
if [ "$rc" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
