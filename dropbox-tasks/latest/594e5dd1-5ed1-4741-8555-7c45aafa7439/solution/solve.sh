#!/bin/bash
set -euo pipefail

# Replace the own-record starter with the fleet-trend lower-edge stringer and rebuild.
cp /solution/main_oracle.c /app/environment/main.c
make -C /app/environment clean
make -C /app/environment

echo "oracle: anode-stringing fleet-trend lower-edge stringer applied"
