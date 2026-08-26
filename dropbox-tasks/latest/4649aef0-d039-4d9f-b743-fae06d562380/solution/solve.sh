#!/bin/bash
set -euo pipefail

mkdir -p /app/src /app/build
cp /solution/reference.cpp /app/src/harmonic_recovery.cpp
g++ -std=c++17 -O2 -Wall -Wextra -pedantic \
  /app/src/harmonic_recovery.cpp -o /app/build/harmonic-recovery
/app/build/harmonic-recovery /app/plant_lab /app/source_spectrum.json
