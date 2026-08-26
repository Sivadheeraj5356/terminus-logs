# `/app/environment` contains `hopledger`, a Go batch processor for relay-mesh hop

- **UUID:** `cfe2f2a7-0da5-44c9-b3b3-c9df0ecc1bae`
- **Slug:** `app-environment-contains-hopledger-a-go-batch-processor-for`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

`/app/environment` contains `hopledger`, a Go batch processor for relay-mesh hop journals. The current implementation handles only the legacy happy path and produces incorrect shift-close artifacts for mixed-version manifests, revised lane records, cancellation tombstones, policy changes, and resumed replay.

Implement the replay contract documented under `/app/environment/docs/` so manifests like `/app/environment/fixtures/manifest.json` produce deterministic `report`, `digest`, and `audit` artifacts through the documented CLI. The tool must create missing output parent directories, reject invalid histories without leaving partial outputs, and make `--resume-tag` output byte-identical to an uninterrupted run over the same manifest.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
