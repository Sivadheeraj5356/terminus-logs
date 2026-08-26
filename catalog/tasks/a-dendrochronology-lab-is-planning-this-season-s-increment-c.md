# A dendrochronology lab is planning this season's increment coring across forty t

Submission: `f43f3ac4-cd80-4082-b695-fa42e643dfcc`  
Slug: `a-dendrochronology-lab-is-planning-this-season-s-increment-c`  
Latest archive: `f43f3ac4-cd80-4082-b695-fa42e643dfcc_submission_2026-07-15T22_28_54.639Z.zip`  
Revisions: 5

## Task summary

A dendrochronology lab is planning this season's increment coring across forty tree-ring sites, `ts-01` through `ts-40`, listed under /app/environment/data. Each site holds a floating ring sequence that is worthless until it is pinned to the regional master, and pinning it takes a single core whose series actually crossdates. Bore a tree and its core either carries a clean, sensitive run of rings that lands cleanly against the master, or it comes up rotten, ring-broken, or too flat to match and settles nothing. That a given core crossdates is chance, governed by a per-core rate `p` fixed by the site, and cores are independent, so committing `n` of them pins a site with probability `1 - (1 - p)^n`; a lone crossdatable series does it. For every site you choose two numbers, cores booked on the cheap shared field crew and cores booked on a dearer contract corer, and you want the total spend as low as it will go while each site still reaches the `anchor_floor` set in /app/environment/data/chronology_policy.json. A starter `dater` already sits in /app/environment, sizing each site from its own past cores alone, and the point is to do better than that. The catch lives in /app/environment/data/core_log.csv. A thin record pins almost nothing: a site whose two logged cores both crossdated can read far stronger than a season will bear out, while the flattest, most complacent sites were bored over and over with never a series landing, so their tally is nearly mute on the rate a fresh season will draw. The fresh season is what the score uses. Each site's real per-core rate for it is...

Required artifacts include: `/app/environment/data`, `/app/environment/data/chronology_policy.json`, `/app/environment`, `/app/environment/data/core_log.csv`, `/app/environment/data/README.md`.

Author anonymous tagged this **hard** scientific-computing task (rust, scientific-computing, estimation, uncertainty, reliability).

Time estimates: expert ~180 min, junior ~480 min.

Harbor timeouts: agent 1800.0s, verifier 1200.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `f43f3ac4-cd80-4082-b695-fa42e643dfcc_submission_2026-07-15T22_28_54.639Z.zip` is a task submission, not a Harbor job. 5 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
