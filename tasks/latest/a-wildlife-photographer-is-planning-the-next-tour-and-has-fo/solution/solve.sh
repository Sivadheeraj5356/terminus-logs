#!/bin/bash
set -euo pipefail

# Swap the own-log starter for the fleet-trend lower-edge framer and rebuild.
cp /solution/main_oracle.rs /app/environment/main.rs
make -C /app/environment clean
make -C /app/environment

echo "oracle: keeper-framing fleet-trend lower-edge framer applied"
