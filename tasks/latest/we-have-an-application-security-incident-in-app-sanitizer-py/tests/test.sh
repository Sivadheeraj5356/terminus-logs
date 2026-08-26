#!/usr/bin/env bash
set -u

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set."
    exit 1
fi

mkdir -p /logs/verifier /tmp/verifier-site

for wheel in /opt/verifier-wheels/*.whl; do
    python3 -m zipfile -e "$wheel" /tmp/verifier-site
done

cd /app
PYTHONPATH=/tmp/verifier-site python3 -m pytest \
    -p no:cacheprovider \
    --ctrf /logs/verifier/ctrf.json \
    /tests/test_outputs.py \
    -rA
RESULT=$?

if [ "$RESULT" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
