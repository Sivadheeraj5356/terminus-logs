# Repair the Haskell tool in `/opt/cnfprep` so `make -C /opt/cnfprep` builds `/opt

Submission: `9bf34249-7c49-45f6-8836-dbef31fe327c`  
Slug: `repair-the-haskell-tool-in-opt-cnfprep-so-make-c-opt-cnfprep`  
Latest archive: `9bf34249-7c49-45f6-8836-dbef31fe327c_submission_2026-07-09T09_36_18.758Z.zip`  
Revisions in Dropbox: 1

## Task summary

Repair the Haskell tool in `/opt/cnfprep` so `make -C /opt/cnfprep` builds `/opt/cnfprep/bin/cnfprep` and the executable preprocesses DIMACS CNF files correctly. In normal mode it runs as `/opt/cnfprep/bin/cnfprep INPUT --out OUT --log LOG --map MAP`. It must write a DIMACS CNF that is equisatisfiable with the input, has no duplicate literals, tautological clauses, unit clauses, pure literals, subsumed clauses, or applicable bounded variable eliminations left, and has a header that matches the emitted clauses. The audit log is line based. It may contain `input`, `assign`, `drop`, `derive`, and `emit` records, but every output clause must appear as exactly one `emit ... 0` record and no `emit` record may describe a clause absent from `OUT`. The map file is also line based: it must contain `n N`, zero or more `f LIT`, `r VAR`, and `e VAR DEFAULT CLAUSE | CLAUSE ...` records sufficient for model extension. Extension mode is invoked as `/opt/cnfprep/bin/cnfprep --extend INPUT --map MAP --model PARTIAL --model-out FULL`; for any satisfying assignment of `OUT` written as `var=0` or `var=1` lines over the remaining variables, it must produce a complete assignment for variables `1..N` that satisfies `INPUT` and preserves those remaining-variable values.

Required artifacts include: not named as `/app` paths.

Author anonymous tagged this **hard** scientific-computing task (haskell, sat, cnf, preprocessing, model-preservation).

Time estimates: expert ~330 min, junior ~660 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=weak, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `9bf34249-7c49-45f6-8836-dbef31fe327c_submission_2026-07-09T09_36_18.758Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
