#!/bin/bash
set -euo pipefail

# Verifier dependencies are installed in environment/Dockerfile.
# Add task-specific verifier-only Python packages there, not here.

mkdir -p /logs/verifier

bash /app/scripts/start_mysql.sh

set +e
python3 -m pytest \
    -o cache_dir=/tmp/pytest_cache \
    --ctrf /logs/verifier/ctrf.json \
    /tests/test_m2.py -rA
RC=$?
if [ "$RC" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
