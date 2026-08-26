# # Multi-arm site fabric

- **UUID:** `f37da340-640d-49f5-9c54-0f753bcae8c8`
- **Slug:** `multi-arm-site-fabric`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

Bring `/etc/sitefab` up for the inventory under `/app/environment/topology/` and keep the sealed controller at `/usr/lib/sitefab` untouched. Drive everything through `/app/bin/sitefab`.

File shapes live in `/app/environment/schema/`. Ops tickets are under `/app/environment/scenarios/`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
