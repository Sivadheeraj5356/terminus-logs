# We've got an entropic mass-transfer lab under /app/environment. The Go and Rust 

Submission: `18179614-cdc5-4c21-af6f-62384a0b204d`  
Slug: `we-ve-got-an-entropic-mass-transfer-lab-under-app-environmen`  
Latest archive: `18179614-cdc5-4c21-af6f-62384a0b204d_submission_2026-07-13T09_21_48.103Z.zip`  
Revisions in Dropbox: 1

## Task summary

We've got an entropic mass-transfer lab under /app/environment. The Go and Rust tree already builds four CLIs, but end-to-end runs still miss the behavioral contract in /app/environment/docs/mass_contract.txt. Correct the sources under /app/environment so every public surface matches that contract. Hand-written files under /app/output are not enough. Rebuild with /app/environment/scripts/rebuild.sh using Go and Rust only (see /app/environment/docs/toolchain.md). Install otctl-run, otctl-probe, otctl-audit, and otctl-inspect under /app/environment/build/.

Required artifacts include: `/app/environment`, `/app/environment/docs/mass_contract.txt`, `/app/output`, `/app/environment/scripts/rebuild.sh`, `/app/environment/docs/toolchain.md`, `/app/environment/build/`, `/app/output/mass_report.json`, `/app/output/plan_trace.csv`.

Author anonymous tagged this **hard** scientific-computing task (optimal-transport, entropic-regularization, log-domain-sinkhorn, wasserstein, numeric-policy).

Time estimates: expert ~150 min, junior ~400 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `18179614-cdc5-4c21-af6f-62384a0b204d_submission_2026-07-13T09_21_48.103Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
