#!/usr/bin/env bash
set -euo pipefail
cd /app/environment
cargo build --release --locked -p grti_matrix_k9
mkdir -p /app/environment/bin
cp /app/environment/target/release/grti_matrix_k9 /app/environment/bin/grti_matrix_k9
