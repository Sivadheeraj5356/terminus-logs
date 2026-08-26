#!/bin/bash
set -euo pipefail
cd /app/environment
cargo build --release -p q7m
mkdir -p /app/environment/bin
cp target/release/q7m /app/environment/bin/q7m
