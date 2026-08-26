# Our `vaultseal` crypto harness gets fuzzed every night and spits out a pile of g

- **UUID:** `6b3ac7d8-fc5d-4da1-8785-f918ca4df0ad`
- **Slug:** `our-vaultseal-crypto-harness-gets-fuzzed-every-night-and-spi`
- **Category:** security
- **Difficulty:** hard

## Summary

Our `vaultseal` crypto harness gets fuzzed every night and spits out a pile of gdb backtraces and valgrind memcheck logs, and a Terraform module in `/app/triage` turns that corpus into a single deterministic `triage_report.json` — classifying each crash, scrubbing key material, correlating the gdb and valgrind sides, clustering near-identical crashes, and failing `terraform apply` when anything trips the severity gate. It was passing its acceptance suite until yesterday's refactor.

It still runs end to end and still writes a report, but the report is now wrong in several places: the refactor introduced regressions in the analysis logic, and they don't all show up on the small sample corpus, so a quick run can look fine while the module is still broken. You have a reference build of the engine — the way it behaved before the refactor — shipped as an opaque binary at `/app/oracle`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
