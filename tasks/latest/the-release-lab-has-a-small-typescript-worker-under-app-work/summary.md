# The release lab has a small TypeScript worker under `/app/worker` that should tu

- **UUID:** `31078c0e-46e8-4ae1-a5f8-34c93862d360`
- **Slug:** `the-release-lab-has-a-small-typescript-worker-under-app-work`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

The release lab has a small TypeScript worker under `/app/worker` that should turn a directory of OCI-style diffusion experiment cards into a deterministic Monte Carlo reduction report. Make the source under `/app/worker` regenerate the report through the normal command; a manual or static JSON write is not sufficient because the verifier reruns the command on the default fixtures and on additional valid input directories.

Please make this command work: `cd /app/worker && npm run report -- --spec-dir /app/worker/fixtures/specs --calibration /app/worker/fixtures/calibrations.json --output /app/output/diffusion-report.json`

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
