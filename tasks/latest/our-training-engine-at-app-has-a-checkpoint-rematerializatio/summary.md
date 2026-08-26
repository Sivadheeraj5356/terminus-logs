# Our training engine at /app has a checkpoint/rematerialization mode that is supp

- **UUID:** `6dabbf20-a99a-41dc-b50b-43f08707febb`
- **Slug:** `our-training-engine-at-app-has-a-checkpoint-rematerializatio`
- **Category:** machine-learning
- **Difficulty:** hard

## Summary

Our training engine at /app has a checkpoint/rematerialization mode that is supposed to be numerically indistinguishable from running without it, but right now checkpointed runs drift away from the baseline a few steps in, and resuming from a mid-run checkpoint doesn't line up with an uninterrupted run either. The engine is the stubbed Rust crate under /app/src.

The op formulas, the per-layer rematerialization schedule, the PRNG and dataset-shuffling scheme, the ragged-last-batch rule, the optimizer update, and the gradient-clipping policy for the unstable third layer are all pinned in /app/spec/engine_design.md — read that first. Implement the tape-based autodiff engine and training loop so that a full run with checkpointing enabled reproduces the loss and gradient norm of the same run with checkpointing disabled at every step, and so that resuming from a checkpoint saved mid-run continues training identically to an uninterrupted run through the remaining steps.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
