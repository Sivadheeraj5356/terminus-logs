#!/usr/bin/env bash
set -euo pipefail

cd /solution
printf '%s\n' "applying lattice crate repairs"
patch -d /app -p0 --batch < ./oracle.patch
cd /app
cargo build --release --locked
