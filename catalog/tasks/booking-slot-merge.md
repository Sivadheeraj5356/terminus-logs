# # Booking Slot Merge

Submission: `2939c523-a9c0-4197-aac6-3849160e4ac2`  
Slug: `booking-slot-merge`  
Latest archive: `2939c523-a9c0-4197-aac6-3849160e4ac2_submission_2026-07-08T05_37_44.138Z.zip`  
Revisions in Dropbox: 1

## Task summary

`slot-merge` coalesces room and resource booking intervals stored as JSONL in `*.slot` files. The verifier rebuilds `/app/target/release/slot-merge` from your source after you edit it. Output from the tool does not always match the rules below.

Required artifacts include: `/app/target/release/slot-merge`.

Author Jay tagged this **hard** debugging task (rust, booking, intervals, merge, scheduling, overlap).

Time estimates: expert ~45 min, junior ~120 min.

Harbor timeouts: agent 600s, verifier 60s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `2939c523-a9c0-4197-aac6-3849160e4ac2_submission_2026-07-08T05_37_44.138Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Agent writes a locally plausible solution that misses a hidden verifier constraint. Agent explores the environment and never produces the required /app or /output artifacts.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
