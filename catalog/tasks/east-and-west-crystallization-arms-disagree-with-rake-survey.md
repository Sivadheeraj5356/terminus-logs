# East and west crystallization arms disagree with rake surveys on multi-day brine

Submission: `5e2448d7-3fca-4f7b-9b5d-e838f740f9df`  
Slug: `east-and-west-crystallization-arms-disagree-with-rake-survey`  
Latest archive: `5e2448d7-3fca-4f7b-9b5d-e838f740f9df_submission_2026-07-12T13_12_26.903Z.zip`  
Revisions in Dropbox: 1

## Task summary

East and west crystallization arms disagree with rake surveys on multi-day brine campaigns. Single-day simulation traces look fine. Continues from mid-tape checkpoints and pack swaps without a cold restart leave routing and front advances out of line with field measurements. `/app/bin/pond_ctl` is the pond simulation driver. It loads the field scenario under `/app/data/active/` and writes `/app/output/front_report.json`. Rebuild with `/app/scripts/build.sh` and invoke with `TB_POND_FIXTURE=1`. The mixed Go/Rust pipeline under `/app` must produce deterministic reports for pond_alpha, pond_beta, pond_gamma, pond_delta, and pond_epsilon with each staged as the active pack. The report includes schema_version, pond_id, mast_epoch, arms, daily_fronts, calm_latch_events, survey_mismatch, front_sum, and digest_hex as named in the comment above main in `/app/cmd/pond_ctl/main.go`.

Required artifacts include: `/app/bin/pond_ctl`, `/app/data/active/`, `/app/output/front_report.json`, `/app/scripts/build.sh`, `/app/cmd/pond_ctl/main.go`.

Author anonymous tagged this **hard** scientific-computing task (simulation, crystallization, wind-rose, numerical, go, rust).

Time estimates: expert ~75 min, junior ~220 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `5e2448d7-3fca-4f7b-9b5d-e838f740f9df_submission_2026-07-12T13_12_26.903Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
