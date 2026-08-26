# This is an exact computer-algebra problem: the continued-fraction expansion, con

Submission: `abb341a4-ba59-41e6-a769-bc996481c53c`  
Slug: `this-is-an-exact-computer-algebra-problem-the-continued-frac`  
Latest archive: `abb341a4-ba59-41e6-a769-bc996481c53c_submission_2026-07-18T06_40_33.539Z.zip`  
Revisions in Dropbox: 1

## Task summary

This is an exact computer-algebra problem: the continued-fraction expansion, convergents, and periodicity of a real algebraic number selected by root index. Every reported quantity is computed in exact arithmetic with no floating point. You are given an integer polynomial and must report the continued fraction of one of its real roots, exactly. The work is done in Julia: the file /app/src/solver.jl already contains the standard-input to standard-output harness, and you complete the compute function it calls. Run it with `julia /app/src/solver.jl`, reading the problem from standard input and printing the answer. Use only the provided files and Julia's standard library, and compute everything with exact arithmetic, Julia's Rational{BigInt} and BigInt, never floating point.

Required artifacts include: `/app/src/solver.jl`.

Author anonymous tagged this **unknown** scientific-computing task (exact-arithmetic, continued-fractions, algebraic-numbers, real-root-isolation, computer-algebra, big-integer).

Time estimates: expert ~300 min, junior ~720 min.

Harbor timeouts: agent 1800.0s, verifier 1800.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `abb341a4-ba59-41e6-a769-bc996481c53c_submission_2026-07-18T06_40_33.539Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
