# The directory /app holds a small offline data-processing tool that turns haul-pe

- **UUID:** `a460ca27-bf77-4620-860d-a4b6b68313bf`
- **Slug:** `the-directory-app-holds-a-small-offline-data-processing-tool`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

The directory /app holds a small offline data-processing tool that turns haul-permit telemetry into a billing-style ledger report. It ingests two structured text files (a quarry-config and a traffic-event stream) and replays the stream against the configured allowances to produce a deterministic ledger, one record per line on standard output.

Run it as:

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
