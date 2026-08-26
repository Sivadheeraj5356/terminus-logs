#!/bin/bash
set -u

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile."
    exit 1
fi

# rebuild-polymorph-chronicle — interpreted Perl; probe install in conftest

set +e
bash -c 'cd /app && /opt/verifier-venv/bin/python -m pytest -rA -o cache_dir=/tmp/pytest_cache \
  --ctrf /logs/verifier/ctrf.json "${TEST_DIR:-/tests}/test_outputs.py"'
if [ $? -eq 0 ]; then
 echo 1 > /logs/verifier/reward.txt
else
 echo 0 > /logs/verifier/reward.txt
fi
