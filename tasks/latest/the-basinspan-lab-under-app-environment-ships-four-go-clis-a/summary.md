# The BasinSpan lab under /app/environment ships four Go CLIs and a Rust merge ker

- **UUID:** `607bed84-a099-419c-9c59-328be106f2dc`
- **Slug:** `the-basinspan-lab-under-app-environment-ships-four-go-clis-a`
- **Category:** machine-learning
- **Difficulty:** hard

## Summary

The BasinSpan lab under /app/environment ships four Go CLIs and a Rust merge kernel for neuron-aligned feedforward weight merging. The tree builds and runs, but campaign output still disagrees with /app/environment/docs/basinspan_contract.txt.

Fix the Go and Rust sources under /app/environment to match that contract, then rebuild with /app/environment/scripts/rebuild.sh (see /app/environment/docs/toolchain.md). Hand-written or static output under /app/output is insufficient; the normal pipeline must regenerate every artifact.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
