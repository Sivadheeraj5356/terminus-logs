# The offline TypeScript workspace under `/app/environment` is incomplete. Repair 

Submission: `40b3aad8-a71a-4b38-ace6-52cded3f3ed7`  
Slug: `the-offline-typescript-workspace-under-app-environment-is-in`  
Latest archive: `40b3aad8-a71a-4b38-ace6-52cded3f3ed7_submission_2026-07-21T05_54_56.205Z.zip`  
Revisions: 1

## Task summary

The offline TypeScript workspace under `/app/environment` is incomplete. Repair source under `/app/environment`. Rebuild with npm. Emit `/app/output/inv_d9.yaml` through the graded validation pipeline in `/app/environment/docs/d9_pact.md`. Static YAML writes are insufficient. Run the driver command in `d9_pact.md` with `--idx-store /app/environment/data/idx_store.db`. Rebuild before validating. Interim YAML under `/app/output/stage/partial.yaml` is not graded.

Required artifacts include: `/app/environment`, `/app/output/inv_d9.yaml`, `/app/environment/docs/d9_pact.md`, `/app/environment/data/idx_store.db`, `/app/output/stage/partial.yaml`, `/app/environment/docs/o8_flow.md`, `/app/environment/docs/i9_enclose.md`, `/app/environment/data/cfg_d9.yaml`.

Author anonymous tagged this **hard** scientific-computing task (hvac-damper, numerical-simulation, interval-enclosure, obligation-eight, floating-point-policy, mi-trace).

Time estimates: expert ~120 min, junior ~360 min.

Harbor timeouts: agent 1800s, verifier 1200s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `40b3aad8-a71a-4b38-ace6-52cded3f3ed7_submission_2026-07-21T05_54_56.205Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
