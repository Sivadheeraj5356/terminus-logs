#!/bin/bash
# Compile the cryostat boil-off warden into /app/cryoctl with Cargo.
# Fully offline: the warmed target/ cache makes this incremental.
set -euo pipefail

cd /app
cargo build --release
cp /app/target/release/cryoctl /app/cryoctl
