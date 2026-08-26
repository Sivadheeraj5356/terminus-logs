#!/bin/bash
set -euo pipefail

# Replace the own-log starter with the board-trend lower-edge planner and rebuild.
cp /solution/main_oracle.rs /app/environment/main.rs
make -C /app/environment clean
make -C /app/environment

echo "oracle: wick-proving board-trend lower-edge planner applied"
