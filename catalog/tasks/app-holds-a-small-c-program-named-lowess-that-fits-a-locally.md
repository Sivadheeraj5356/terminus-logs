# `/app` holds a small C program named `lowess` that fits a locally weighted

Submission: `44abc022-6927-410e-973d-52aabff705be`  
Slug: `app-holds-a-small-c-program-named-lowess-that-fits-a-locally`  
Latest archive: `44abc022-6927-410e-973d-52aabff705be_submission_2026-07-15T21_44_22.702Z.zip`  
Revisions in Dropbox: 6

## Task summary

`/app` holds a small C program named `lowess` that fits a locally weighted scatterplot smoothing (LOWESS) curve to scattered `(x, y)` data. The standard-input decoding and the standard-output formatting in `/app/lowess.c` are already wired up and working; what is missing is the numerical core, the `lowess_fit` function, which right now just echoes the raw `y`-values back so the program runs without actually smoothing anything. Your job is to implement it so the fitted values match the governing standard. Keep the implementation in `/app/lowess.c` as source-based C that can be rebuilt into the `lowess` executable with a standard C compiler and `libm`; use no external dependencies and no network access. The program reads a single JSON object from standard input of the shape `{"x":[...],"y":[...],"frac":<float>,"it":<int>,"delta":<float>}` and writes exactly one line to standard output: a compact JSON array of the smoothed `y`-values fitted at each input `x`, given in the original input order and printed with full double precision. `frac` is the fraction of the data used in each local regression, `it` is the number of robustifying iterations, and `delta` is the interpolation-skip distance.

Required artifacts include: `/app/lowess.c`, `/app/SPEC.md`.

Author anonymous tagged this **hard** scientific-computing task (numerical-methods, regression, smoothing, nonparametric, statistics).

Time estimates: expert ~150 min, junior ~360 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `44abc022-6927-410e-973d-52aabff705be_submission_2026-07-15T21_44_22.702Z.zip` is a task submission, not a Harbor job. 6 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
