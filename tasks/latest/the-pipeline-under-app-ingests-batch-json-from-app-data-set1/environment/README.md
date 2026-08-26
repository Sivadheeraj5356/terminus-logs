# Feature Ancestry Drift Pipeline

Run from `/app`:

```
cargo build --release --bin pipeline
cargo run --bin pipeline -- --states data/ --output artifacts/
```

Audit existing artifacts:

```
cargo run --bin pipeline -- --check --output artifacts/
```

See `/app/docs/data_spec.md` for artifact contracts.
