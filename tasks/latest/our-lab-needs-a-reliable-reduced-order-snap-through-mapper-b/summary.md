# Our lab needs a reliable reduced-order snap-through mapper before the next kirig

- **UUID:** `f63761db-9e93-4aa3-a47f-c31771e96774`
- **Slug:** `our-lab-needs-a-reliable-reduced-order-snap-through-mapper-b`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

Our lab needs a reliable reduced-order snap-through mapper before the next kirigami test series. Put the C++ implementation in `/app/workbench/main.cpp`, `/app/workbench/model.cpp`, and `/app/workbench/solver.cpp`, with any required headers beside them.

Those sources must compile into an executable supporting `--input <absolute JSON path>` and `--output <absolute JSON path>`. It must evaluate any campaign allowed by `/app/docs/analysis-contract.md`; the files in `/app/cases` are only sanity checks and are not the complete input set.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
