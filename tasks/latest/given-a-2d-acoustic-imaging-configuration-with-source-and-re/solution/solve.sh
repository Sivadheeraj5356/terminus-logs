#!/bin/bash
set -euo pipefail

cd /app

mkdir -p bin
cp /solution/fwi_ultrasound.cpp fwi_ultrasound.cpp
g++ -O2 -std=c++17 -o bin/fwi_ultrasound fwi_ultrasound.cpp

mkdir -p /app/output
/app/bin/fwi_ultrasound --config /app/config/settings.json --data-dir /app/data/fwi --output /app/output/fwi_report.json

echo "Completed successfully"
