# # Booking Slot Merge

Submission: `2939c523-a9c0-4197-aac6-3849160e4ac2`  
Slug: `booking-slot-merge`  
Latest archive: `2939c523-a9c0-4197-aac6-3849160e4ac2_submission_2026-07-08T05_37_44.138Z.zip`  
Revisions: 1

## Task summary

`slot-merge` coalesces room and resource booking intervals stored as JSONL in `*.slot` files. The verifier rebuilds `/app/target/release/slot-merge` from your source after you edit it. Output from the tool does not always match the rules below.

Required artifacts include: `/app/target/release/slot-merge`.

Author Jay tagged this **hard** debugging task (rust, booking, intervals, merge, scheduling, overlap).

Time estimates: expert ~45 min, junior ~120 min.

Harbor timeouts: agent 600s, verifier 60s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Harbor trials: 1 — 1 solved, 0 valid fail, 0 timeout, 0 infra.

## Agent summary

Skipping image OS validation for hb__6c7d33acfdfa3ac2438c0bf8c187cd08: docker inspect returned 1 Collecting main service artifacts

## Stump the models?

- oracle: 0/1 valid fail (0.0%)
- Timeouts excluded: 0; infra excluded: 0
- Band: `too_easy`
