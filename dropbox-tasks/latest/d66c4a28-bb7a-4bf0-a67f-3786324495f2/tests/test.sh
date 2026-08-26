#!/bin/bash

mkdir -p /logs/verifier /app/out
echo 0 > /logs/verifier/reward.txt

# Check if we're in a valid working directory
if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile before running this script."
    exit 1
fi

# Defensively build the derive tool if the agent hasn't produced it yet.
if [ ! -x /app/build/derive ]; then
    cmake -B /app/build -S /app -DCMAKE_BUILD_TYPE=Release 2>&1
    CONFIGURE_RC=$?
    BUILD_RC=1
    if [ "$CONFIGURE_RC" -eq 0 ]; then
        cmake --build /app/build -j"$(nproc)" 2>&1
        BUILD_RC=$?
    fi
    if [ "$BUILD_RC" -ne 0 ]; then
        echo 0 > /logs/verifier/reward.txt
        exit 0
    fi
fi

# Run tests
python3 -m pytest -o cache_dir=/tmp/pytest_cache \
  --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA
RC=$?
if [ "$RC" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
