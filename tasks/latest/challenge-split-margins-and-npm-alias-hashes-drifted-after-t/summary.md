# Challenge-split margins and npm alias hashes drifted after the last scorer pass

- **UUID:** `61c6130c-7dbb-4ce8-bd91-7843ea62ed4a`
- **Slug:** `challenge-split-margins-and-npm-alias-hashes-drifted-after-t`
- **Category:** machine-learning
- **Difficulty:** hard

## Summary

Challenge-split margins and npm alias hashes drifted after the last scorer pass on the r01 moderation bundle. Eval rows can look stable while group metrics and provenance nodes do not.

Fix the C++ sources under `/app/environment` so rebuilding that tree and running `r01_score` against `/app/environment/r01` regenerates `/app/output/moderation_ledger.json` from the bundled inputs. Hand-written JSON or skipping the built binary is not enough.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
