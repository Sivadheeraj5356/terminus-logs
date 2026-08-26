# Complete the native Rust source under `/app/environment` so `/app/bin/forest-aud

- **UUID:** `0eca009c-c711-4f52-9d59-abc6b0e82c12`
- **Slug:** `complete-the-native-rust-source-under-app-environment-so-app`
- **Category:** machine-learning
- **Difficulty:** hard

## Summary

Complete the native Rust source under `/app/environment` so `/app/bin/forest-audit` evaluates the bounded integer decision forest in `/app/data/demo.forest` against the stateful audit script in `/app/data/demo.audit` and writes `/app/output/certificates.json`. The command must also accept exactly three absolute positional paths in the order model, audit, and output; relative paths are invalid.

The public contract in `/app/docs/forest-audit.md` defines the model and audit records, validation priority, nested `PUSH` and `POP` state behavior, exact counterfactual comparison, canonical report and hash, diagnostics, and safe publication rules. The completed command must handle other valid bounded forests and audit sessions, preserve an existing destination and any symbolic-link target on every failure, and rebuild with `cargo build --release --locked --offline`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
