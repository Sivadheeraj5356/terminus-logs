# # volatile scope sweep ledger rebuild

Submission: `4b6650cb-9e59-4011-928d-09eb581dd523`  
Slug: `volatile-scope-sweep-ledger-rebuild`  
Latest archive: `4b6650cb-9e59-4011-928d-09eb581dd523_submission_2026-07-07T16_30_39.756Z.zip`  
Revisions in Dropbox: 3

## Task summary

Volatile-path scope journals rotated during maintenance, and operators now see `/app/output/sweep_ledger.json`, `/app/output/probe_snapshot.json`, and `/app/state/scope_state.json` drift from the VSW1 fixtures, overlays, and profile manifests. Counts look plausible but window boundaries skew, cross-bucket sequence-gap rollups disagree, digests fail an independent roll, merge collapses distinct scope/mask pairs or scans journals with the wrong slack, and probe still reports a stale cache width or pre-overlay mask after manifest rotation. Repair the Rust sources under `/app/environment` so the normal pipeline regenerates artifacts. Hand-written JSON, fixture edits, or wrapper-only changes are insufficient.

Required artifacts include: `/app/output/sweep_ledger.json`, `/app/output/probe_snapshot.json`, `/app/state/scope_state.json`, `/app/environment`, `/app/environment/target/release/volsweep`, `/app/environment/docs/profiles.md`, `/app/environment/docs/`, `/app/environment/ops/sweep.cache`.

Author anonymous tagged this **hard** system-administration task (rust, tmpfiles, volatile, scope, replay).

Time estimates: expert ~180 min, junior ~480 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `4b6650cb-9e59-4011-928d-09eb581dd523_submission_2026-07-07T16_30_39.756Z.zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
