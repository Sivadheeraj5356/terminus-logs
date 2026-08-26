# `/app` holds a small C program named `lowess` that fits a locally weighted

- **UUID:** `44abc022-6927-410e-973d-52aabff705be`
- **Slug:** `app-holds-a-small-c-program-named-lowess-that-fits-a-locally`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

`/app` holds a small C program named `lowess` that fits a locally weighted scatterplot smoothing (LOWESS) curve to scattered `(x, y)` data. The standard-input decoding and the standard-output formatting in `/app/lowess.c` are already wired up and working; what is missing is the numerical core, the `lowess_fit` function, which right now just echoes the raw `y`-values back so the program runs without actually smoothing anything.

Your job is to implement it so the fitted values match the governing standard. Keep the implementation in `/app/lowess.c` as source-based C that can be rebuilt into the `lowess` executable with a standard C compiler and `libm`; use no external dependencies and no network access.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
