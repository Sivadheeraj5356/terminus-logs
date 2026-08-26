#!/bin/bash
set -euo pipefail
cd /app
patch -p1 < /solution/solution.patch
cargo build --release --locked
