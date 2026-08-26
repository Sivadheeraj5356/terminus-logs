# A scanner records the parallel-beam projections of an unknown image from many an

- **UUID:** `151e606e-7d19-4cce-9868-34f9b6addd5e`
- **Slug:** `a-scanner-records-the-parallel-beam-projections-of-an-unknow`
- **Category:** scientific-computing
- **Difficulty:** medium

## Summary

A scanner records the parallel-beam projections of an unknown image from many angles, the way a slice scanner captures how much a slice absorbs along each ray, and packs one batch of those scans into a single binary container. We need a Go program that reads the container, recovers the scans, reports each recovered sinogram, and reconstructs the original image on its pixel grid.

Compile it to a binary at /app/ctrecon; a stub main.go that compiles but returns nothing is at /app/main.go for you to replace. It reads one JSON object on standard input and writes one JSON object on standard output, one result per scan in the batch, in order.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
