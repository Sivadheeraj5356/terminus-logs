# Challenge-split margins and npm alias hashes drifted after the last scorer pass 

Submission: `61c6130c-7dbb-4ce8-bd91-7843ea62ed4a`  
Slug: `challenge-split-margins-and-npm-alias-hashes-drifted-after-t`  
Latest archive: `61c6130c-7dbb-4ce8-bd91-7843ea62ed4a_submission_2026-07-17T08_01_25.164Z.zip`  
Revisions in Dropbox: 1

## Task summary

Challenge-split margins and npm alias hashes drifted after the last scorer pass on the r01 moderation bundle. Eval rows can look stable while group metrics and provenance nodes do not. Fix the C++ sources under `/app/environment` so rebuilding that tree and running `r01_score` against `/app/environment/r01` regenerates `/app/output/moderation_ledger.json` from the bundled inputs. Hand-written JSON or skipping the built binary is not enough.

Required artifacts include: `/app/environment`, `/app/environment/r01`, `/app/output/moderation_ledger.json`, `/app/environment/r01/docs/c1.txt`, `/app/environment/r01/docs/c2.txt`.

Author anonymous tagged this **hard** machine-learning task (moderation, toxicity, robustness, provenance, cpp).

Time estimates: expert ~90 min, junior ~240 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `61c6130c-7dbb-4ce8-bd91-7843ea62ed4a_submission_2026-07-17T08_01_25.164Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
