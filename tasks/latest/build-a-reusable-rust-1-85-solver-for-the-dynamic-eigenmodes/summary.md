# Build a reusable Rust 1.85 solver for the dynamic eigenmodes of a three-layer co

- **UUID:** `191831ec-7a1c-499e-afeb-2d567fe8fa69`
- **Slug:** `build-a-reusable-rust-1-85-solver-for-the-dynamic-eigenmodes`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

Build a reusable Rust 1.85 solver for the dynamic eigenmodes of a three-layer composite thermal rod. Write Rust 2021 source to `/app/thermal_modes.rs`, compile it with the standard library only to `/app/thermal_modes`, and expose exactly `/app/thermal_modes --input-dir DIR --output-dir DIR`.

The program processes every immutable `*.case` file in the input directory and creates one `<name>.json` report per case. Run it on `/app/thermal_problem/cases` so `/app/thermal_mode_results` contains exactly `alloy.json`, `basalt.json`, `ceramic.json`, `glass.json`, and `graphite.json`; never modify an input file.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
