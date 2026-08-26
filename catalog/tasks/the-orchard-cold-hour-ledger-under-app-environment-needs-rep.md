# The orchard cold-hour ledger under `/app/environment` needs repair. Rebuild the 

Submission: `5f068a1b-7c07-450e-9c4f-68f394628d61`  
Slug: `the-orchard-cold-hour-ledger-under-app-environment-needs-rep`  
Latest archive: `5f068a1b-7c07-450e-9c4f-68f394628d61_submission_2026-07-09T11_12_42.063Z.zip`  
Revisions: 3

## Task summary

The orchard cold-hour ledger under `/app/environment` needs repair. Rebuild the Go CLI from source so replay mode regenerates deterministic `s7_ledger.jsonl`, `s7_audit.tsv`, and `replay_state.json` artifacts from manifest-relative inputs, while the original simple mode remains backward compatible. The repaired pipeline must follow the contracts in `/app/environment/docs` for profile settings, environment overrides, sensor registry calibration, correction replay, Fahrenheit conversion, anchored bucket windows, interval credit, deterministic output, replay state, and atomic failure behavior.

Required artifacts include: `/app/environment`, `/app/environment/docs`.

Author anonymous tagged this **hard** scientific-computing task (go, orchard, chill-hours, agronomy, ledger, replay).

Time estimates: expert ~240 min, junior ~480 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `5f068a1b-7c07-450e-9c4f-68f394628d61_submission_2026-07-09T11_12_42.063Z.zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
