# The clinical operations team needs a Rust CLI under `/app` that rebuilds hospita

- **UUID:** `67c458ba-2129-47c1-aa33-9f3c39c48140`
- **Slug:** `the-clinical-operations-team-needs-a-rust-cli-under-app-that`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

The clinical operations team needs a Rust CLI under `/app` that rebuilds hospital census and procedure analytics from CSV event feeds. Build and run: ```bash cd /app && cargo build --release --locked cd /app && ./target/release/hospital_analytics --input-dir /app/data --output /app/output/analytics_report.json ```

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
