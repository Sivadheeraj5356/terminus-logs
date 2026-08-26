# Aurelia's regulator publishes civil-time ordinances, and since the 1991 amendmen

- **UUID:** `eddac55d-8f97-4c03-b225-40d1828b90ca`
- **Slug:** `aurelia-s-regulator-publishes-civil-time-ordinances-and-sinc`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

Aurelia's regulator publishes civil-time ordinances, and since the 1991 amendments landed our zone files have disagreed with them for at least three jurisdictions. Bookings in the affected zones sit an hour off across half of every year.

The ordinances are the source of truth now. They live under /app/data/ordinances, one directory per jurisdiction, with each jurisdiction's meridian recorded alongside them.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
