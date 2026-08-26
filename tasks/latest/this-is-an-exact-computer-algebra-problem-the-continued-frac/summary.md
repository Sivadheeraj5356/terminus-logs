# This is an exact computer-algebra problem: the continued-fraction expansion, con

- **UUID:** `abb341a4-ba59-41e6-a769-bc996481c53c`
- **Slug:** `this-is-an-exact-computer-algebra-problem-the-continued-frac`
- **Category:** scientific-computing
- **Difficulty:** unknown

## Summary

This is an exact computer-algebra problem: the continued-fraction expansion, convergents, and periodicity of a real algebraic number selected by root index. Every reported quantity is computed in exact arithmetic with no floating point.

You are given an integer polynomial and must report the continued fraction of one of its real roots, exactly. The work is done in Julia: the file /app/src/solver.jl already contains the standard-input to standard-output harness, and you complete the compute function it calls.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
