# The lab under `/app` exercises offline integrity measurement and appraisal enfor

- **UUID:** `e3085bc3-fe09-4d0e-8814-9fad0d5e396a`
- **Slug:** `the-lab-under-app-exercises-offline-integrity-measurement-an`
- **Category:** security
- **Difficulty:** hard

## Summary

The lab under `/app` exercises offline integrity measurement and appraisal enforcement across split policy authorities. A Go lowering pass resolves the authority pin at `/app/data/authority/pin.json` under `/app/data/authority/`, materializes attachments from the resolved policy bundle (production attachments also live under `/app/data/policy.json`) into `/app/output/program.json`, and a Rust replay worker records `/app/output/read_traces.json` and `/app/output/measure_log.json`.

A reconcile pass rolls manifest attestation into `/app/output/integrity_report.json`. Rebuild with `bash /app/scripts/build.sh`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
