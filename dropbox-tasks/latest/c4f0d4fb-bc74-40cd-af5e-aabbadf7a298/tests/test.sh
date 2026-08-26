#!/usr/bin/env bash

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

cat > /logs/verifier/ctrf.json << 'CTRF'
{"results":{"tool":{"name":"pytest"},"summary":{"tests":0,"passed":0,"failed":0,"pending":0,"skipped":0,"other":0},"tests":[]}}
CTRF

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set."
    echo 0 > /logs/verifier/reward.txt
    exit 0
fi

# Verify integrity of protected files
TRACE_HASH=$(sha256sum /app/environment/traces/match_trace.csv 2>/dev/null | awk '{print $1}')
TOOL_HASH=$(sha256sum /app/environment/tools/elo_verify/main.rs 2>/dev/null | awk '{print $1}')

EXPECTED_TRACE="16a0774f092a00fd4a24ca613af79367ad575347f0acd16b6e283965f1309516"
EXPECTED_TOOL="2b252f8734163040a2d21bbd6763a9492d69ff7140187b0e01862c06020e8182"

if [ "$TRACE_HASH" != "$EXPECTED_TRACE" ]; then
    echo "Error: trace file integrity check failed"
    echo 0 > /logs/verifier/reward.txt
    exit 0
fi

if [ "$TOOL_HASH" != "$EXPECTED_TOOL" ]; then
    echo "Error: elo_verify source integrity check failed"
    echo 0 > /logs/verifier/reward.txt
    exit 0
fi

cd /app

bash /app/environment/scripts/rebuild.sh 2>&1 || {
    echo "Error: cargo build failed"
    echo 0 > /logs/verifier/reward.txt
    exit 0
}

if [ -f /app/environment/target/release/elo_verify ]; then
    cp /app/environment/target/release/elo_verify /app/environment/elo_verify
fi

set +e
python3 -m pytest --ctrf /logs/verifier/ctrf.json "${TEST_DIR:-/tests}/test_outputs.py" -rA -v
rc=$?
if [ "$rc" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
