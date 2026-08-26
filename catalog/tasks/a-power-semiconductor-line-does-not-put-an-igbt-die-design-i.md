# A power-semiconductor line does not put an IGBT die design into production on a 

Submission: `776d5450-2fdf-4bcd-a833-5703b8ed002c`  
Slug: `a-power-semiconductor-line-does-not-put-an-igbt-die-design-i`  
Latest archive: `776d5450-2fdf-4bcd-a833-5703b8ed002c_submission_2026-07-20T14_45_11.215Z.zip`  
Revisions in Dropbox: 13

## Task summary

A power-semiconductor line does not put an IGBT die design into production on a hunch. A die earns its design a place only by passing the whole acceptance in a single sitting: it holds off the rated collector-emitter voltage in the blocking state, keeps its on-state drop inside the saturation window, and rides out a short-circuit pulse without latching. Fail any one of the three and it is scrapped. How readily a design yields a die that clears all three is fixed by how the design landed in fab, a per-die rate `p`; build `n` dies and the design is released the moment one of them passes, at `1 - (1 - p)^n`. Forty candidate designs are on this slate, `ig-01` through `ig-40` under /app/environment/data. For each one you set two counts: how many dies to carry on the fab's own in-house probe, and how many to hand to an outside test house. Both routes run the identical acceptance, so a die's chance of passing is the same either way; the routes differ only in price and in how many the cheap one will take. The starter `switcher` in /app/environment takes the easy road, pinning each design's rate to that design's own thin log and nothing else.

Required artifacts include: `/app/environment/data`, `/app/environment`, `/app/environment/data/release_rule.json`, `/app/environment/data/test_log.csv`, `/app/environment/data/README.md`.

Author anonymous tagged this **hard** scientific-computing task (rust, scientific-computing, estimation, uncertainty, reliability).

Time estimates: expert ~180 min, junior ~480 min.

Harbor timeouts: agent 1800.0s, verifier 1200.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `776d5450-2fdf-4bcd-a833-5703b8ed002c_submission_2026-07-20T14_45_11.215Z.zip` is a task submission, not a Harbor job. 13 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
