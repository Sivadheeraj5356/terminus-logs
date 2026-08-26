# The Rust seating driver under `/app` still produces inconsistent live state when

Submission: `ecacd7da-f89d-4706-9705-ba07177f1740`  
Slug: `the-rust-seating-driver-under-app-still-produces-inconsisten`  
Latest archive: `ecacd7da-f89d-4706-9705-ba07177f1740_submission_2026-07-15T17_12_37.374Z.zip`  
Revisions: 1

## Task summary

The Rust seating driver under `/app` still produces inconsistent live state when schedules combine repeated seat publications, cycle transitions, catalog probes, and failed runs. Repair the editable Rust sources under `/app/src` so module-level journal loading, replay, publication, digest, and recovery behavior exposed through the compiled binary is correct, not only static or hand-written output files. Normal seat, recovery seat, and shift-table probe modes documented in `/app/docs/overview.md` must satisfy the observable contracts in `/app/docs/overview.md` and `/app/docs/runtime_notes.txt`, including correct live-ledger totals, cycle ownership, cache isolation, deterministic publication, and rollback behavior. Journal rows are applied in ascending `seq` order. Rows sharing a `seq` are identical only when their parsed `op`, `scenario_tag`, `cycle_epoch`, `ram_block_id`, and `event_id` fields match; identical repeats apply once, while a mismatch is a durable-sequence conflict that must exit non-zero before any requested final log or report is changed or created. For a non-empty `event_id`, only the first row in durable order applies. Normal seat runs append to an existing seat log without changing its prior bytes and assign new emitted `seq` values from one greater than the greatest existing value, or from 1 when no prior value exists. Recovery preserves every row that existed before the invocation byte-for-byte, inspects all valid pre-existing log rows, and begins newly emitted recovery rows at one greater than the highest existing integer `seq` (or 1 when no prior...

Required artifacts include: `/app/src`, `/app/docs/overview.md`, `/app/docs/runtime_notes.txt`, `/app/output/seat_log.jsonl`, `/app/output/seat_report.json`, `/app/environment/Cargo.toml`.

Author anonymous tagged this **hard** system-administration task (rust, state-machine, journal-replay, operator-tooling, regression).

Time estimates: expert ~120 min, junior ~300 min.

Harbor timeouts: agent 1800s, verifier 1200s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `ecacd7da-f89d-4706-9705-ba07177f1740_submission_2026-07-15T17_12_37.374Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
