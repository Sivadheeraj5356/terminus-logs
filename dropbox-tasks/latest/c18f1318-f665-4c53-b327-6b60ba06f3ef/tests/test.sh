#!/bin/bash
# All test dependencies are pre-installed in the image (pytest in /opt/venv). Every check
# runs against data files generated at test time and never touches the network, so the
# verifier always completes offline. No package installation happens here.
set -uo pipefail

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Set a WORKDIR in the Dockerfile." >&2
    exit 1
fi

cd /tests
PYTHONSAFEPATH=1 /opt/venv/bin/pytest -o cache_dir=/tmp/pytest_cache test_outputs.py -rA --ctrf /logs/verifier/ctrf.json --rootdir=/tests --confcutdir=/tests
rc=$?
if [ "$rc" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
