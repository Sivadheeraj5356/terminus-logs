# Our measurement pipeline profiles empirical histograms whose true modes come

Submission: `c18f1318-f665-4c53-b327-6b60ba06f3ef`  
Slug: `our-measurement-pipeline-profiles-empirical-histograms-whose`  
Latest archive: `c18f1318-f665-4c53-b327-6b60ba06f3ef_submission_2026-07-20T23_37_56.178Z.zip`  
Revisions in Dropbox: 1

## Task summary

Our measurement pipeline profiles empirical histograms whose true modes come out oversplit by sampling noise, and the consolidation has to be self-consistent — this is a fixed-point statistics computation, not a general data-processing utility. Every bin first climbs to the lowest-position heaviest bin inside its radius window, looking again from each stop until it settles, which yields the initial modes and their basins. Then the weak modes dissolve in rounds: the mass bar is derived from the surviving mode count itself — the floor of the total mass over the sharpness times the number of survivors — every basin strictly under the bar dissolves at once, each dissolved basin is handed whole to the surviving mode nearest its own mode with ties to the lower position, and the bar is recomputed from the shrunken mode set, so one dissolution can drag further modes under on the next pass. An optional guard directive caps how many dissolved basins a given mode may ever absorb across the whole run, and once that cap is spent the nearest search has to walk past it to the next eligible mode. Independent of any directive, a mode that ever holds an outright majority of the total mass is sealed for the remainder of the consolidation and can take on no further dissolved basin — a ceiling that emerges from the masses alone and is written nowhere in the input — so a dissolving basin whose nearest survivor is a sealed mode belongs instead to the next nearest mode still open, with the plain nearest rule governing only when every open mode is spent. The iteration ends the first time a...

Required artifacts include: `/app/consolidate`, `/app/output/result.json`, `/app/SPEC.md`.

Author anonymous tagged this **medium** scientific-computing task (java, scientific-computing, statistics, histogram-analysis, numerical-computing).

Time estimates: expert ~150 min, junior ~360 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `c18f1318-f665-4c53-b327-6b60ba06f3ef_submission_2026-07-20T23_37_56.178Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
