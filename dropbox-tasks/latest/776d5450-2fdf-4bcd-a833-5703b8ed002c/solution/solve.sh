#!/bin/bash
set -euo pipefail

# Swap the own-log starter for the slate-fit lower-edge builder and rebuild.
cp /solution/main_oracle.rs /app/environment/main.rs
make -C /app/environment clean
make -C /app/environment

echo "oracle: slate-fit lower-edge switcher applied"
