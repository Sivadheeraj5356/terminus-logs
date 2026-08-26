#!/bin/bash
set -euo pipefail

# Swap the log-only starter for the network-trend lower-edge dater and rebuild.
cp /solution/main_oracle.rs /app/environment/main.rs
make -C /app/environment clean
make -C /app/environment

echo "oracle: crossdate-sizing network-trend lower-edge dater applied"
