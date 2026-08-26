# You administer the site's software license-seat station, which provisions entitl

- **UUID:** `b1d7c1b1-ab3a-41a0-b348-a6f9f96b6d5d`
- **Slug:** `you-administer-the-site-s-software-license-seat-station-whic`
- **Category:** system-administration
- **Difficulty:** medium

## Summary

You administer the site's software license-seat station, which provisions entitlement seats to onboarding accounts from the pool of covered seats. Its overnight allocation stage is unfinished: finish `/app/license/` so the night's request feed turns into the JSON allocation file the morning operators work from: node /app/bin/seat-allocate /app/data/onboarding_requests.ndjson /app/out/allocation.json

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
