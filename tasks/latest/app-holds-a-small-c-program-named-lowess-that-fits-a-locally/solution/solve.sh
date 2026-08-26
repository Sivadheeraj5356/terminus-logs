#!/bin/bash
# Oracle: drop the complete smoother into /app, rebuild, and smoke-run it.
set -euo pipefail

cd /app

# Install the reference implementation over the stub.
cp /solution/lowess.c /app/lowess.c
cp /solution/Makefile /app/Makefile

# Force a fresh build of the smoother binary.
make clean
make

# Smoke test: a simple upward trend smooths to a near-linear fit.
echo '{"x":[1,2,3,4,5],"y":[1.0,2.1,1.3,3.6,2.3],"frac":0.6,"it":0,"delta":0.0}' \
    | ./lowess
