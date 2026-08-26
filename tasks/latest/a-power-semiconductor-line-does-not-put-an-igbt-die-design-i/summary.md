# A power-semiconductor line does not put an IGBT die design into production on a

- **UUID:** `776d5450-2fdf-4bcd-a833-5703b8ed002c`
- **Slug:** `a-power-semiconductor-line-does-not-put-an-igbt-die-design-i`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

A power-semiconductor line does not put an IGBT die design into production on a hunch. A die earns its design a place only by passing the whole acceptance in a single sitting: it holds off the rated collector-emitter voltage in the blocking state, keeps its on-state drop inside the saturation window, and rides out a short-circuit pulse without latching.

Fail any one of the three and it is scrapped. How readily a design yields a die that clears all three is fixed by how the design landed in fab, a per-die rate `p`; build `n` dies and the design is released the moment one of them passes, at `1 - (1 - p)^n`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
