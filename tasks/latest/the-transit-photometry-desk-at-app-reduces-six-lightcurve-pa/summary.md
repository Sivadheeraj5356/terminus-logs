# The transit photometry desk at `/app` reduces six lightcurve packs under `/app/c

- **UUID:** `716c7e42-795e-438c-9b8e-300243fb9428`
- **Slug:** `the-transit-photometry-desk-at-app-reduces-six-lightcurve-pa`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

The transit photometry desk at `/app` reduces six lightcurve packs under `/app/curves` (trap01, warmj, nept, hotspot, graze, quiet). A pack run straight through agrees with the independent ledger `/app/scripts/ref-depth` at the campaign cursor.

Resuming a pack from its mid-campaign checkpoint keeps the residual column small, but the depth product at that cursor no longer matches the straight-through path, and resuming the same checkpoint a second time can land on a different value than the first for several packs. Nothing crashes; the divergence is numerical.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
