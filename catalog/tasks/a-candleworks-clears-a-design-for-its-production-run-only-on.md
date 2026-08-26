# A candleworks clears a design for its production run only once it has thrown a c

Submission: `fd313533-fb55-45aa-9a30-7883983ac956`  
Slug: `a-candleworks-clears-a-design-for-its-production-run-only-on`  
Latest archive: `fd313533-fb55-45aa-9a30-7883983ac956_submission_2026-07-21T03_51_12.728Z.zip`  
Revisions: 5

## Task summary

A candleworks clears a design for its production run only once it has thrown a clean burn: one candle poured to that recipe, burning down to a full even melt pool, no channel tunnelled through the middle, no soot off the wick, no drowned flame. Forty recipes are up for the coming run, `cd-01` through `cd-40` in /app/environment/data/designs.csv, and pouring is not repeatable to the last detail: the wick sits a hair off centre one time and true the next, so one candle off a recipe can burn clean where the one before it faulted. Each design therefore has a clean-burn rate `p` of its own that no single candle reveals, and pouring `n` candles to it lands at least one clean burn with probability `1 - (1 - p)^n`. For every design you return two counts, how many candles for the in-house line and how many for the outside chandler. A starter already sits in /app/environment; it sizes each design from that design's own logged burns alone, and the task is to do better than that. Where the starter goes wrong is the record it trusts. /app/environment/data/burn_log.csv holds the burns already run, and for a good many designs it is a candle or two deep, sometimes a short string of faults with no clean burn set down yet. A record that short is consistent with a wide spread of true rates, and it reads high rather than low, so a design that has barely been poured looks safer than it has earned. The run is judged on the true rates you never get to see, not on the record, and it is settled on the single weakest design of the forty against `burn_floor` in...

Required artifacts include: `/app/environment/data/designs.csv`, `/app/environment`, `/app/environment/data/burn_log.csv`, `/app/environment/data/run_program.json`, `/app/environment/main.rs`, `/app/environment/data/README.md`.

Author anonymous tagged this **hard** scientific-computing task (rust, scientific-computing, estimation, uncertainty, reliability).

Time estimates: expert ~180 min, junior ~480 min.

Harbor timeouts: agent 1800.0s, verifier 1200.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `fd313533-fb55-45aa-9a30-7883983ac956_submission_2026-07-21T03_51_12.728Z.zip` is a task submission, not a Harbor job. 5 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
