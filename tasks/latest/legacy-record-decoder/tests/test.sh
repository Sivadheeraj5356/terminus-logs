#!/bin/bash

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile."
    exit 1
fi

# Remove any stale bundle to force regeneration.
rm -f /app/output/legacy_record_bundle.json

# Rebuild the Rust sources and tools.
echo "[test.sh] Building workspace..."
/app/environment/scripts/build_all.sh
if [ $? -ne 0 ]; then
    echo "Build failed."
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

# Generate the bundle.
echo "[test.sh] Generating bundle..."
/app/environment/tools/bin/xscope --all-samples --bundle-out /app/output/legacy_record_bundle.json
if [ $? -ne 0 ]; then
    echo "Bundle generation failed."
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

# Run tests.
echo "[test.sh] Running tests..."
pytest --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA

if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi

