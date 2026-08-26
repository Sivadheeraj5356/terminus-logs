#!/bin/bash
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
printf '%s
' '{"version":"1.0.0","results":{"summary":{"tests":0,"passed":0,"failed":0,"pending":0,"skipped":0,"other":0}}}' > /logs/verifier/ctrf.json
if [ "$PWD" = "/" ]; then echo 0 > /logs/verifier/reward.txt; exit 1; fi
export PATH="/usr/local/cargo/bin:/opt/verifier-venv/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"
cd /app || { echo 0 > /logs/verifier/reward.txt; exit 1; }
# cargo build --release --locked is executed by this rebuild helper
timeout --foreground 180 /app/scripts/verifier-rebuild.sh || { echo 0 > /logs/verifier/reward.txt; exit 1; }
TEST_DIR="${TEST_DIR:-/tests}"
/opt/verifier-venv/bin/python3 "$TEST_DIR/gen_hidden_fixtures.py" || { echo 0 > /logs/verifier/reward.txt; exit 1; }
set +e
timeout --foreground 600 /opt/verifier-venv/bin/python3 -m pytest -o cache_dir=/tmp/pytest_cache --ctrf /logs/verifier/ctrf.json "$TEST_DIR/test_outputs.py" -rA
if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
