#!/bin/bash
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set."
    exit 1
fi

cd /app

if [ ! -f bin/fwi_ultrasound ]; then
    mkdir -p bin
    if [ -f fwi_ultrasound.cpp ]; then
        g++ -O2 -std=c++17 -o bin/fwi_ultrasound fwi_ultrasound.cpp 2>&1
    else
        echo "No source file found"
        exit 0
    fi
fi

BUILD_RC=$?
if [ $BUILD_RC -ne 0 ]; then
    echo "Build failed with exit code $BUILD_RC"
    exit 0
fi

mkdir -p /app/output
/app/bin/fwi_ultrasound --config /app/config/settings.json --data-dir /app/data/fwi --output /app/output/fwi_report.json || true

pytest --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -v -rA

if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
