#!/bin/bash
set -uo pipefail

if [ "$PWD" = "/" ]; then
    mkdir -p /logs/verifier
    echo 0 > /logs/verifier/reward.txt
    exit 0
fi

mkdir -p /logs/verifier
STATUS=0
DATA_FILE="/app/environment/data/bank_additional.csv"
BASELINE_DIR="/tmp/public_snapshot"

restore_public_data() {
    if [ -f "$BASELINE_DIR/bank_additional.csv" ]; then
        cp "$BASELINE_DIR/bank_additional.csv" "$DATA_FILE" 2>/dev/null || true
        chmod a+r "$DATA_FILE" 2>/dev/null || true
    fi
}

run_candidate() {
    chmod 600 /tests/labels.csv 2>/dev/null || true
    chmod 777 /app/environment 2>/dev/null || true
    chmod a+r /app/environment/analysis.R 2>/dev/null || true
    chmod -R a+rX /app/environment/data 2>/dev/null || true
    rm -rf /app/environment/outputs
    mkdir -p /app/environment/outputs
    chmod 777 /app/environment/outputs
    su -s /bin/sh nobody -c "cd /app/environment && HOME=/tmp TMPDIR=/tmp PATH=/usr/local/bin:/usr/bin:/bin Rscript /app/environment/analysis.R" || true
}

run_pytest() {
    /opt/test-venv/bin/python -m pytest \
        --ctrf /logs/verifier/ctrf.json -q -rA -p no:cacheprovider \
        /tests/test_outputs.py
}

trap restore_public_data EXIT

run_candidate
run_pytest
rc=$?
[ "$rc" -ne 0 ] && STATUS=1

if [ "$STATUS" -eq 0 ]; then
    rm -rf "$BASELINE_DIR"
    mkdir -p "$BASELINE_DIR" || STATUS=1
    chmod 700 "$BASELINE_DIR" 2>/dev/null || true
    cp "$DATA_FILE" "$BASELINE_DIR/bank_additional.csv" || STATUS=1
    cp /app/environment/outputs/predictions.csv "$BASELINE_DIR/predictions.csv" || STATUS=1
    cp /app/environment/outputs/metrics.json "$BASELINE_DIR/metrics.json" || STATUS=1
    chmod 600 "$BASELINE_DIR"/* 2>/dev/null || true
fi

if [ "$STATUS" -eq 0 ]; then
    /opt/test-venv/bin/python /tests/generate_permuted_data.py || STATUS=1
fi

if [ "$STATUS" -eq 0 ]; then
    run_candidate
    BASELINE_OUTPUT_DIR="$BASELINE_DIR" run_pytest
    rc=$?
    [ "$rc" -ne 0 ] && STATUS=1
fi

restore_public_data

if [ "$STATUS" -eq 0 ]; then
    /opt/test-venv/bin/python /tests/generate_hidden_data.py || STATUS=1
fi

if [ "$STATUS" -eq 0 ]; then
    run_candidate
    run_pytest
    rc=$?
    [ "$rc" -ne 0 ] && STATUS=1
fi

restore_public_data

test "$STATUS" -eq 0
rc=$?
if [ "$rc" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
