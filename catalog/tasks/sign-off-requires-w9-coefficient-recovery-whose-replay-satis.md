# Sign-off requires w9 coefficient recovery whose replay satisfies every tolerance

Submission: `62c01bd9-0317-4cad-8a76-ef95efdbaae7`  
Slug: `sign-off-requires-w9-coefficient-recovery-whose-replay-satis`  
Latest archive: `62c01bd9-0317-4cad-8a76-ef95efdbaae7_submission_2026-07-15T04_17_53.718Z.zip`  
Revisions: 1

## Task summary

Sign-off requires w9 coefficient recovery whose replay satisfies every tolerance class in `/app/docs/w9_rules.md`. Holdout dynamics under `/app/data/v9/segments/` currently disagree with q9 profile calibration under `/app/data/q9/`. Update modules under `/app/environment` so `node /app/environment/z9/w9_once.js` regenerates `/app/out/coeff_v9.json` and `/app/out/trace_v9.log`. Field names blend_weights, link_scalar, forcing, bands, profiles, p7_rms, p8_rms, phase_lag, segment_a_rms_x, segment_a_rms_y, segment_b_rms_x, segment_b_rms_y, and band_row are defined in the contract doc. Class E band checks compare replay slots against the read-only sidecar table; holdout forward agreement reports per-segment rms_x and rms_y prey/predator RMS statistics in trace_v9. Consecutive replays must yield byte-identical artifacts. Static writes to either output path are insufficient.

Required artifacts include: `/app/docs/w9_rules.md`, `/app/data/v9/segments/`, `/app/data/q9/`, `/app/environment`, `/app/environment/z9/w9_once.js`, `/app/out/coeff_v9.json`, `/app/out/trace_v9.log`.

Author anonymous tagged this **hard** scientific-computing task (ecology, ode, parameter-estimation, numeric-policy, model-calibration, scientific-computing).

Time estimates: expert ~45 min, junior ~180 min.

Harbor timeouts: agent 900s, verifier 300s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `62c01bd9-0317-4cad-8a76-ef95efdbaae7_submission_2026-07-15T04_17_53.718Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
