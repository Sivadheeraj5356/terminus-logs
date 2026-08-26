# # Quota supervisor drift after unclean shutdown

Submission: `666e51d2-cacf-4f2d-b4cc-7080dde6666b`  
Slug: `quota-supervisor-drift-after-unclean-shutdown`  
Latest archive: `666e51d2-cacf-4f2d-b4cc-7080dde6666b_submission_2026-07-12T12_33_43.939Z.zip`  
Revisions: 1

## Task summary

Storage operators finished an emergency reboot of the local quota control plane, but fleet state still disagrees with itself. `/app/bin/client_t4 list` reports hard limits that diverge from `/app/environment/data/q9/rows_q2.json`, sidecar stamps under `/app/environment/data/m9/` lag sealed generations, and deferred journal tails under `/app/environment/data/j4/` can resurrect limits for labels already retired in the catalog. Restore correct cold-boot recovery through the deployed operator toolchain under `/app/environment` so `/app/bin/ctl_s8 recover-all` completes cleanly, then rebuild with `/app/environment/scripts/build_all.sh`. Wrapper-only edits or static writes under `/app/output` are insufficient; graded artifacts must come from the normal admin pipeline.

Required artifacts include: `/app/bin/client_t4`, `/app/environment/data/q9/rows_q2.json`, `/app/environment/data/m9/`, `/app/environment/data/j4/`, `/app/environment`, `/app/bin/ctl_s8`, `/app/environment/scripts/build_all.sh`, `/app/output`.

Author anonymous tagged this **hard** system-administration task (sysadmin, storage, quota, journal, crash-recovery, filesystem).

Time estimates: expert ~45 min, junior ~150 min.

Harbor timeouts: agent 900s, verifier 600s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `666e51d2-cacf-4f2d-b4cc-7080dde6666b_submission_2026-07-12T12_33_43.939Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
