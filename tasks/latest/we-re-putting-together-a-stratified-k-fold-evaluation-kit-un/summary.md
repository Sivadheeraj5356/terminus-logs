# We're putting together a stratified k-fold evaluation kit under `/app` so a labe

- **UUID:** `5bd7c1a8-74f0-448f-b30f-f088169b9fe8`
- **Slug:** `we-re-putting-together-a-stratified-k-fold-evaluation-kit-un`
- **Category:** machine-learning
- **Difficulty:** hard

## Summary

We're putting together a stratified k-fold evaluation kit under `/app` so a labeled cohort CSV becomes deterministic fold IDs plus stratification diagnostics that a later CV or training loop can trust without redoing the split. The kit assigns folds and measures label balance; it does not train or score a model.

Field shapes, digests, and seals are defined in `/app/schema/fold_manifest.schema.json` and `/app/schema/fold-digest-contracts.md`. Build with `mvn -q -f /app/pom.xml package`, then run `/app/bin/foldctl assemble --dataset PATH --folds K --label COLUMN` (that wrapper must exec the shaded jar under `/app/target` with Java).

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
