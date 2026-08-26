# Operators report a frustrating pattern in our bundled network configuration lab:

- **UUID:** `32b1eb87-ee7a-4f3c-a5ae-5258ef7a156d`
- **Slug:** `operators-report-a-frustrating-pattern-in-our-bundled-networ`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

Operators report a frustrating pattern in our bundled network configuration lab: declarative apply banners return success, status listings show updated rows, yet live links keep old address masks and routes. Daemon listing traces disagree with address-equivalent probes and with regenerated observation rows for the same replay sequence.

Rapid apply sequences leave stale daemon cache rows visible while declarative stamps already advanced. Repair the C source code under `/app/environment` so the normal pipeline regenerates `/app/output/n8_observations.json`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
