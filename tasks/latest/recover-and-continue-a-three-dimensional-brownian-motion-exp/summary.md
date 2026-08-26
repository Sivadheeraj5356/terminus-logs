# Recover and continue a three-dimensional Brownian-motion experiment from particl

- **UUID:** `90861d6b-54c0-493e-86f8-f17b71361d72`
- **Slug:** `recover-and-continue-a-three-dimensional-brownian-motion-exp`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

Recover and continue a three-dimensional Brownian-motion experiment from particle records embedded in a partially corrupted Apptainer definition. The scientific work now has three stages: create a canonical laboratory checkpoint from an initial definition, resume that checkpoint when immutable prior shards are accompanied by new shards, and rebuild the DuckDB dataset and diffusion report from the checkpoint alone.

The authoritative contract is `/app/environment/docs/diffusion-recovery-protocol.md`. Build the supplied offline Java/JDBC harness with `/app/environment/build.sh`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
