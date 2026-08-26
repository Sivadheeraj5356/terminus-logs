# Static-pod hash certification for node profiles p7 and p8 is broken. Repair the

- **UUID:** `ec9aaa9c-66c5-4adc-9656-d68fc126b85f`
- **Slug:** `static-pod-hash-certification-for-node-profiles-p7-and-p8-is`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

Static-pod hash certification for node profiles p7 and p8 is broken. Repair the watcher sources under `/app/environment` so the normal pipeline regenerates `/app/output/feasibility_certificate.json` with no violations.

Matrix traversal is sorted set filename, source item order, then p7 followed by p8. Unit tags contain all sorted label tokens, including arbitrary keys such as rollout; annex-enabled profiles also contain only annotations matching the configured annex prefix in the configured relative order.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
