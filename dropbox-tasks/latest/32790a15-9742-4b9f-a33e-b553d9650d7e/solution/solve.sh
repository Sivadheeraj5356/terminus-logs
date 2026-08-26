#!/usr/bin/env bash
# Oracle overlay: restore contamination eval metric + inference feature scoring
# WINCONTAM_ORACLE_OVERLAY context-window-contamination-risk-analyzer
set -euo pipefail
PATH="/usr/local/cargo/bin:${PATH}"
cd /app

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/fixed"
[ -d "$ROOT" ] || ROOT=/solution/fixed
[ -d "$ROOT" ] || { echo "fixed missing" >&2; exit 1; }

install -d /app/src/ctxhold /app/src/turnclock /app/src/causechain /app/src/featmetrics /app/src/freezeout /app/src/decoy
install -m 0644 "$ROOT/wc_oracle_bin.rs" /app/src/main.rs
install -m 0644 "$ROOT/ctxhold/wc_ctxhold.rs" /app/src/ctxhold/wc_ctxhold.rs
install -m 0644 "$ROOT/turnclock/wc_turnclock.rs" /app/src/turnclock/wc_turnclock.rs
install -m 0644 "$ROOT/causechain/wc_causechain.rs" /app/src/causechain/wc_causechain.rs
install -m 0644 "$ROOT/featmetrics/wc_featmetrics.rs" /app/src/featmetrics/wc_featmetrics.rs
install -m 0644 "$ROOT/freezeout/wc_freezeout.rs" /app/src/freezeout/wc_freezeout.rs
install -m 0644 "$ROOT/decoy/wc_tokendiag.rs" /app/src/decoy/wc_tokendiag.rs

env CARGO_INCREMENTAL=0 /usr/local/cargo/bin/cargo build --release --locked --offline
test -x /app/target/release/wincontam

S=/tmp/wincontam-verify-store
O=/tmp/wincontam-verify-out.json
rm -rf "$S"; mkdir -p "$S"
/app/target/release/wincontam absorb-context-hold --corpus /app/data --store "$S"
/app/target/release/wincontam score-contam-window --corpus /app/data --store "$S" --cutoff 2024-06-01T00:00:00Z --emitted-at 2024-06-01T12:00:00Z --out "$O"
/app/target/release/wincontam emit-risk-bulletin --corpus /app/data --store "$S" --cutoff 2024-06-01T00:00:00Z --emitted-at 2024-06-01T12:00:00Z --out /tmp/wincontam-verify-pack.json
python3 -c 'import json,pathlib; d=json.loads(pathlib.Path("/tmp/wincontam-verify-out.json").read_text()); print("ok", len(d["contam_rows"]))'
