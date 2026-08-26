# The offline Sigstore model-signing deploy gate under `/app/environment` is suppo

- **UUID:** `185c0116-5994-4fef-88cf-842385e2adb7`
- **Slug:** `the-offline-sigstore-model-signing-deploy-gate-under-app-env`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

The offline Sigstore model-signing deploy gate under `/app/environment` is supposed to prove foreign-cloud signing principals cannot authorize home-cloud workload deploys after approval revoke windows (including cert validity windows, counter-sign quorum floors, and stale signing-cache residue). Independent deploy-probe replay must agree with the published package; local signing-witness success is not enough.

That proof does not hold today. Repair the sources under `/app/environment` so `bash /app/environment/scripts/weld_bin.sh` then `bash /app/environment/tools/mx_run.sh gate --out /app/output/mx_pack.json` emits a schema-valid package at that path.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
