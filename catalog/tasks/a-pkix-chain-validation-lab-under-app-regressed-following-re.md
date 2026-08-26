# A PKIX chain-validation lab under `/app` regressed following reload-frame work. 

Submission: `c4b1314f-7e2b-4798-aad5-d4b802d9839b`  
Slug: `a-pkix-chain-validation-lab-under-app-regressed-following-re`  
Latest archive: `c4b1314f-7e2b-4798-aad5-d4b802d9839b_submission_2026-07-06T15_53_54.378Z.zip`  
Revisions in Dropbox: 1

## Task summary

A PKIX chain-validation lab under `/app` regressed following reload-frame work. `/app/bin/run_chainlab` reads `/app/data/rotation_spec.txt` and publishes `/app/output/trace.json` with `/app/output/readout.csv`, but isolated replay from `/app/target/release/probe` reports different generation samples, link carry, consult refusal, and row mapping on identical rotation inputs. Multi-tick cases show blk_marks climbing from a stale baseline. Link carry overshoots or lags the live peak. Consult refusal tracks decoration cells, not the harness pulled view. Fresh case frames pick up generation history left by the prior case tail. trace.json lists cases cold_tick, link_ticks, rotate_hold, and harness-woven twin_leaf. Each case includes tag, blk_marks, and tries with wire_tag, carry_at_try, latch_denied, and key. readout.csv carries tag and latch_denied mirroring final try refusal per tag per `/app/docs/contract.md`.

Required artifacts include: `/app/bin/run_chainlab`, `/app/data/rotation_spec.txt`, `/app/output/trace.json`, `/app/output/readout.csv`, `/app/target/release/probe`, `/app/docs/contract.md`, `/app/environment`.

Author anonymous tagged this **medium** security task (rust, pkix, x509, trust-store, chain-validation).

Time estimates: expert ~45 min, junior ~180 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `c4b1314f-7e2b-4798-aad5-d4b802d9839b_submission_2026-07-06T15_53_54.378Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
