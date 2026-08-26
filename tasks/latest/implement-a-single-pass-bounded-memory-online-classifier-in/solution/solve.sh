#!/bin/bash
set -euo pipefail

mkdir -p /app/environment/src
cp /solution/Solver.java /app/environment/src/Solver.java
javac /app/environment/src/Solver.java
java -cp /app/environment/src Solver /app/environment/data > /tmp/household-power-gapaware-submeter-ewma-smoke.json
