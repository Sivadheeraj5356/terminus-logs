# # Orchard harvest crate mass-balance settlement

- **UUID:** `02035d55-3b98-4031-b9f7-3fcf2af065cc`
- **Slug:** `orchard-harvest-crate-mass-balance-settlement`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

Orchard pickup settlement on the HARVEST1 lane is failing metrology QA. The pick-balance driver reads newline-delimited capture rows (pick, tare, supersede, spoilage) from an input feed and writes a per-zone balance report under /app/output.

Independent replay audits report mismatches across generation ordering, tare offset windows and gram-band thresholds, void and refusal cadence, capacity accounting, zone label identity, settlement tie precedence, stamp lineage, and checkpoint resume parity. The gram-conservation metrology model, checkpoint schema, digest preimages, and report fields are normative in /app/docs/harvest_rules.txt.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
