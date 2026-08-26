# A displacement field u(x, t) on the periodic interval x in [0, 1) obeys the damp

- **UUID:** `f0d52f86-7534-43e8-8e2c-b3f3b73212b2`
- **Slug:** `a-displacement-field-u-x-t-on-the-periodic-interval-x-in-0-1`
- **Category:** scientific-computing
- **Difficulty:** unknown

## Summary

A displacement field u(x, t) on the periodic interval x in [0, 1) obeys the damped wave equation u_tt + 2 g u_t = c squared times u_xx, with positive wave speed c and positive damping g. The interval wraps and the field starts from rest, so its initial time derivative is zero.

A C project in /app supplies the driver, parser, grid, profile sampling, and CSV writer, leaving only the time integrator. Implement scheme_advance, declared in /app/include/scheme.h and stubbed in /app/src/scheme.c, advancing the state in place between successive times.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
