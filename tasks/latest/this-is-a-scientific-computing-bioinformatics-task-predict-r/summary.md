# This is a scientific-computing bioinformatics task: predict RNA secondary struct

- **UUID:** `fc31f5ee-7fc4-424f-999c-89dc3ac48a58`
- **Slug:** `this-is-a-scientific-computing-bioinformatics-task-predict-r`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

This is a scientific-computing bioinformatics task: predict RNA secondary structure under the RNPX-12 folding model. RNPX-12 scores folded RNA structures using thermodynamic parameters, chemical-probing reactivity, and guide-channel evidence.

For each RNA instance, determine the maximum-scoring secondary structure and report the scientific audit records required by `/app/docs/model_reference.md`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
