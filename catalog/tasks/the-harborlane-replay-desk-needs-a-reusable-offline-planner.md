# The harborlane replay desk needs a reusable offline planner, not a one-off plan 

Submission: `df101f67-b1f1-41ce-b7fa-5b65d20e1d7e`  
Slug: `the-harborlane-replay-desk-needs-a-reusable-offline-planner`  
Latest archive: `df101f67-b1f1-41ce-b7fa-5b65d20e1d7e_submission_2026-07-08T15_06_40.813Z.zip`  
Revisions: 1

## Task summary

The harborlane replay desk needs a reusable offline planner, not a one-off plan for the sample files. Finish the Haskell program at `/app/Main.hs`; it will be compiled with GHC and run as `/tmp/harborlane-planner --root ROOT --out-dir OUT_DIR`. For each `ROOT`, read `ROOT/var/lib/harborlane/data/segments.tsv`, `ROOT/var/lib/harborlane/data/replay.tsv`, `ROOT/var/lib/harborlane/data/conflicts.tsv`, `ROOT/etc/harborlane/policy.tsv`, and `ROOT/var/cache/harborlane/state/leases.tsv`. Write `OUT_DIR/plan.tsv` and `OUT_DIR/Plan.hs`. The public data root is `/`, but the same binary must work for other roots with the same schema. Do not edit input files, fetch packages, use the network, or call external helper programs from the Haskell planner.

Required artifacts include: `/app/Main.hs`.

Author Anonymous tagged this **hard** data-processing task (haskell, optimization, replay-planning, risk-modeling, data-processing).

Time estimates: expert ~720.0 min, junior ~4800.0 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Harbor trials: 1 — 1 solved, 0 valid fail, 0 timeout, 0 infra.

## Agent summary

Skipping image OS validation for hb__d955e7e2937d4722a38465bb584c1a18: docker inspect returned 1 Collecting main service artifacts

## Stump the models?

- oracle: 0/1 valid fail (0.0%)
- Timeouts excluded: 0; infra excluded: 0
- Band: `too_easy`
