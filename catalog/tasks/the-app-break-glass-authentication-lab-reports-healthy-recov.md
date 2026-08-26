# The `/app` break-glass authentication lab reports healthy recovery probes yet di

Submission: `49f5490e-9e2f-4905-8968-eab1f4159d0f`  
Slug: `the-app-break-glass-authentication-lab-reports-healthy-recov`  
Latest archive: `49f5490e-9e2f-4905-8968-eab1f4159d0f_submission_2026-07-09T06_05_58.247Z.zip`  
Revisions in Dropbox: 2

## Task summary

The `/app` break-glass authentication lab reports healthy recovery probes yet disagreeing login, session, checkpoint, and replay projections. Fix the lab sources and authored policy so the public verification workflow completes and emits `/app/reports/recovery-proof.json`. Regenerated `/app/runtime/pam.d` stacks must track policy regeneration from source. `recovery-proof.json` carries `policy_source_sha256`, `policy_runtime_sha256`, audit counts, `state_converged`, and `collision_token` (`fresh` with main recovery token consumed in the public collision flow). Operator must restore a PAM break-glass lab so faillock lockout, one-use recovery under auth_err and ignore password outcomes, policy regeneration into runtime stacks, journal-backed session/audit projections, and checkpoint rewind all converge under the public verification workflow.

Required artifacts include: `/app/reports/recovery-proof.json`, `/app/runtime/pam.d`.

Author anonymous tagged this **hard** system-administration task (pam, authentication, policy-compiler, state-replay, audit, checkpoint).

Time estimates: expert ~240 min, junior ~600 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `49f5490e-9e2f-4905-8968-eab1f4159d0f_submission_2026-07-09T06_05_58.247Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
