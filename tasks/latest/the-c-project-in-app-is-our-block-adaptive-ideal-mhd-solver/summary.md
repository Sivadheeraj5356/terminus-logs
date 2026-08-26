# The C++ project in /app is our block-adaptive ideal-MHD solver, but the numerics

- **UUID:** `064c4f2e-0120-40f7-aed0-1603c157de74`
- **Slug:** `the-c-project-in-app-is-our-block-adaptive-ideal-mhd-solver`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

The C++ project in /app is our block-adaptive ideal-MHD solver, but the numerics are unfinished. Finish it so that `make` in /app produces /app/bin/amr_mhd and that executable actually advances two-dimensional ideal magnetohydrodynamics with constrained transport on a two-level, block-adaptive Cartesian mesh, exactly as /app/docs/mhd-ct-spec.md lays out.

The framework around the solver — the command line, the case and checkpoint formats, the equation-of-state helpers, the initial-condition presets, the time loop and the diagnostics — is already in place; what is stubbed out is the physics: the reconstruction and Riemann flux, the constrained-transport electric field, the coarse-fine synchronisation, the prolongation and restriction between levels, and the refinement criterion. Right now the stubbed core leaves the field frozen and never refines, so it meets none of the acceptance properties.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
