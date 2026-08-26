#!/bin/bash
set -euo pipefail

cd /app
patch -p1 < /solution/fix.patch
cargo build --release
cp /app/target/release/cryoctl /app/cryoctl
