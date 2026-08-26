# arena_cli

From `/app`, produce `/app/target/release/arena_cli` with:

```
cargo build --release --locked
```


## Commands

### Fresh run

```
/app/target/release/arena_cli run --scenario <name> --out /app/output/runs
```

The name selects `/app/data/<name>.toml`.

Bundled scenario stems include flat, belt, and long. Local ops may also write temporary files under `/app/data/` when exercising control seats, wrap exchanges, and journal continuation, including stems such as c1_base, c1_torus, c2_base, c2_torus, c3_base, c3_torus, d1_torus, d2_a, d2_b, d3_ok, e1_full, e1_journal, e2_journal, e1_resume, and e2_resume.

Mode flat uses axial coordinates without periodic bounds. Mode belt uses axial coordinates with periodic bounds on both axes.

Each fresh run writes one JSON file under `/app/output/runs` named after the scenario.

### Resume

```
/app/target/release/arena_cli resume --journal /app/data/long.toml --out /app/output/runs --tag long_resume
```

Loads the saved move list from the journal section, rebuilds history, then continues remaining moves. Writes a JSON file under `/app/output/runs` named after the tag.

### Optional seed override

```
--seed <u64>
```

Overrides the seed field from the scenario file. Digests and history stay deterministic for a fixed seed.
