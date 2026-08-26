# # Desiccator tray registry replay

- **UUID:** `8d619c9e-6b9a-4728-a6c0-653e45e9050e`
- **Slug:** `desiccator-tray-registry-replay`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

The stdlib-only Rust sources at `/app/desiccator_tray_src/` are a partial, broken tray-registry replay tool: they do not compile, and once they build the behavior still disagrees with the normative contract in `/app/task_file/schema.md` in more than one place. Repair the sources in place so they build and match that contract, then install the release binary at `/app/bin/desiccator_tray` (`/app/bin` is on `PATH`).

`schema.md` is the source of truth for the field tables, per-op field profile, output shape, reject reasons, and the seed run's expected totals — read it in full and repair every deviation you find. Do not edit the schema or anything under `/app/task_file/`, and do not add `serde` or any other crate; emit the JSON by hand.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
