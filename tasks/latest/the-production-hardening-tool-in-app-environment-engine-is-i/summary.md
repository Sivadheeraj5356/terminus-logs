# The production hardening tool in `/app/environment/engine` is incomplete. Implem

- **UUID:** `f3c99fb2-3111-4ea4-b3c6-01306ddfebf1`
- **Slug:** `the-production-hardening-tool-in-app-environment-engine-is-i`
- **Category:** security
- **Difficulty:** hard

## Summary

The production hardening tool in `/app/environment/engine` is incomplete. Implement the exported asynchronous function `hardenMediaInferenceDefaults(repoRoot, dossierPath, fixtureDir, outDir)` and keep `/app/environment/engine/cli/harden.js` working.

For any dossier that follows the included decision-record format, resolve the unique currently ratified production policy, update both `/app/environment/engine/config/inference.js` and `/app/environment/engine/terraform/production.tfvars`, then evaluate every fixture listed by `/app/environment/fixtures/manifest.json` through the bundled local model. Repeated calls in the same process must use the newly supplied dossier and repository state.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
