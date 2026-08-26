# This is a hand-off of a half-finished groundwater model in `/app`. The site setu

- **UUID:** `fa7188e0-c8ed-4560-928a-b504057dcb16`
- **Slug:** `this-is-a-hand-off-of-a-half-finished-groundwater-model-in-a`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

This is a hand-off of a half-finished groundwater model in `/app`. The site setup is in `/app/site_config.json`, and `/app/model_notes.md` defines the transport physics, numerical behavior, sampling rules, well interpolation, and output details.

The current transport and sampling modules are stubbed, so the reported risk numbers are not usable. Implement the reusable JavaScript logic in `/app/simulate.js`, `/app/step_transport.js`, and `/app/sample_aquifer_params.js`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
