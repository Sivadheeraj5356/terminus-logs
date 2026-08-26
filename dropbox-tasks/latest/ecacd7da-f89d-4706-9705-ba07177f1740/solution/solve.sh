#!/usr/bin/env bash
set -euo pipefail

cd /app

FIXED=/solution/fixed

cp "$FIXED/normal_run.rs" src/normal_run.rs
cp "$FIXED/seat_gate.rs" src/seat_gate.rs
cp "$FIXED/replay.rs" src/replay.rs
cp "$FIXED/ledger.rs" src/ledger.rs
cp "$FIXED/journal.rs" src/journal.rs
cp "$FIXED/journal_lanes.rs" src/journal_lanes.rs
cp "$FIXED/operator_view.rs" src/operator_view.rs
cp "$FIXED/state_digest.rs" src/state_digest.rs
cp "$FIXED/mass.rs" src/mass.rs
cp "$FIXED/staged_run.rs" src/staged_run.rs
cp "$FIXED/recover_run.rs" src/recover_run.rs
cp "$FIXED/recovery.rs" src/recovery.rs
cp "$FIXED/publication.rs" src/publication.rs
cp "$FIXED/yard_index.rs" src/yard_index.rs
cp "$FIXED/lane_exercise.rs" src/lane_exercise.rs

cargo build --release --locked
install -m 0755 target/release/compactor_seat /app/bin/compactor_seat

mkdir -p /app/output
/app/bin/compactor_seat --seat /app/fixtures/run_alpha.jsonl \
  --emit-log /app/output/seat_log.jsonl \
  --emit-report /app/output/seat_report.json
