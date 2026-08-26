# Timeline naming after clock step-back

- **UUID:** `896a541d-ead3-45b4-a24a-c1f548ab0594`
- **Slug:** `timeline-naming-after-clock-step-back`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

Timeline naming after clock step-back Fleet nodes show snapper timeline rows that disagree after an NTP step-back and warm restart. WAL batches arrived in directory listing order while checkpoint artifacts still claim an older handoff generation.

Locale catalog excerpts and bind-mount alias rows look plausible in isolation until replay walks profiles out of catalog order.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
