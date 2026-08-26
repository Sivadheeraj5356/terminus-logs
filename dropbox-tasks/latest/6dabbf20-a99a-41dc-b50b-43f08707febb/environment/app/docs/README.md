# tape-engine

A small tape-based reverse-mode autodiff training engine with activation
rematerialization, deterministic PRNG-driven dropout and shuffling, an Adam
optimizer, and resumable checkpoints. Everything of substance is specified in
[../spec/engine_design.md](../spec/engine_design.md); start there.

## Layout

- `src/` — the engine crate (std-only, no external dependencies).
- `spec/engine_design.md` — the design note and the pinned numeric contract.
- `data/` — the fixed synthetic dataset and its manifest.
- `tests_fixtures/` — the run seed and the resume point read at runtime.

## Build and run

The crate builds offline against the standard library:

```
cargo build --release --offline
```

The `sqlite3` command-line tool is available for writing the run database. Run
modes and flags are documented in the design note (section 18); the three
canonical runs are:

```
./target/release/engine --mode nocheckpoint
./target/release/engine --mode checkpoint
./target/release/engine --mode resume
```

They populate `/app/out/runs.db`.
