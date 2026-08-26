#!/bin/bash
set -euo pipefail

cd /app
mkdir -p /tmp/containment-scheduler
rustc --edition 2021 -C opt-level=3 /solution/solver.rs -o /tmp/containment-scheduler/solver
/tmp/containment-scheduler/solver
