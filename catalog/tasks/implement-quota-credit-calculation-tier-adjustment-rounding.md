# Implement quota credit calculation, tier adjustment rounding, and premium holdba

Submission: `de387fcd-522e-4484-8dbd-895fbfd96e55`  
Slug: `implement-quota-credit-calculation-tier-adjustment-rounding`  
Latest archive: `de387fcd-522e-4484-8dbd-895fbfd96e55_submission_2026-07-06T17_17_28.117Z.zip`  
Revisions: 1

## Task summary

Implement quota credit calculation, tier adjustment rounding, and premium holdback logic in the coinsurance-engine module. Keep indemnity share, pipeline order, and tier adjustment basis from the prior step intact. Compute quota credit on indemnity share using each row's `coinsuranceBase` for rate selection per `/app/docs/config-keys.md` and `/app/docs/quota-addendum.md`, not raw `grossIncurred`. Use `quota.credit.rate` unless both quota line and large loss line apply, then use `coinsurance.rate.quota.premium`. Premium holdback rates apply when `coinsuranceBase >= coinsurance.threshold.large.loss`, not from policy tier alone.

Required artifacts include: `/app/docs/config-keys.md`, `/app/docs/quota-addendum.md`, `/app/docs/rounding-schedule.md`, `/app/docs/premium-holdback-addendum.md`.

Author anonymous tagged this **hard** data-processing task (java, maven, bigdecimal, config-files, coinsurance-recovery, multi-module).

Time estimates: expert ~150 min, junior ~300 min.

Harbor timeouts: agent Nones, verifier Nones.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `de387fcd-522e-4484-8dbd-895fbfd96e55_submission_2026-07-06T17_17_28.117Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Agent writes a locally plausible solution that misses a hidden verifier constraint. Agent explores the environment and never produces the required /app or /output artifacts.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
