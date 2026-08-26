# # Mission readiness governance desk

Submission: `9b8419bb-5b2a-493c-acfd-ab51f7d02b23`  
Slug: `mission-readiness-governance-desk`  
Latest archive: `9b8419bb-5b2a-493c-acfd-ab51f7d02b23_submission_2026-07-17T16_21_19.077Z.zip`  
Revisions: 4

## Task summary

Fix the source under /app/environment so the Mission Readiness Review Board command regenerates a consistent determination from a supplied record directory. Build and run /app/bin/boardctl review with a record directory, policy JSON, output directory, and persistent state file; an optional clear-state switch empties prior state before the review. The verifier uses /app/environment/data/policy_standard.json, bundled orbital records, and generated records that change evidence order, policy floors, shared state, repeated reviews of the same case, overdue commitments, and invalid authority declarations. Go and Rust toolchains are installed in the image. After editing sources under /app/environment, rebuild /app/bin/boardctl with go build from /app/environment targeting cmd/boardctl, and rebuild the index helper with `cargo build --release --locked --manifest-path /app/environment/z4/Cargo.toml` (install the release binary as /app/bin/ixcore). Confirm both builds succeed before relying on regenerated artifacts; the verifier also rebuilds from your sources.

Required artifacts include: `/app/environment`, `/app/bin/boardctl`, `/app/environment/data/policy_standard.json`, `/app/environment/z4/Cargo.toml`, `/app/bin/ixcore`, `/app/output/determination.json`, `/app/output/evidence_matrix.csv`, `/app/output/board_memo.txt`.

Author anonymous tagged this **hard** system-administration task (go, rust, spaceflight-ops, readiness-review, governance, state-recovery).

Time estimates: expert ~240 min, junior ~480 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `9b8419bb-5b2a-493c-acfd-ab51f7d02b23_submission_2026-07-17T16_21_19.077Z.zip` is a task submission, not a Harbor job. 4 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
