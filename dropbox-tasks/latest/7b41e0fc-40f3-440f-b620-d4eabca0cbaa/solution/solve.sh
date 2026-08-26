#!/bin/bash
set -euo pipefail

bw_log() { echo "[bw-oracle] $*"; }

bw_log "apply patch bundle"
cd /solution
patch -d /app/environment -p1 --forward --batch < oracle.patch

bw_log "compile m6_ctl release"
cd /app/environment
cargo build --release --locked
install -m755 /app/target/release/m6_ctl /app/bin/m6_ctl
rm -rf /app/output/bw_emit.json /app/output/stream_sidecar.bin /app/var/lane_cache
/app/bin/m6_ctl matrix-all
test -s /app/output/bw_emit.json
test -s /app/output/stream_sidecar.bin
bw_log "matrix pass complete"
