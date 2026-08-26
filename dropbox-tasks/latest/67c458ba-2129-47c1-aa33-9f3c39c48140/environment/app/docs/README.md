# Hospital Analytics Engine

Rust CLI that rebuilds ward census, patient status, and procedure totals from
historical hospital event feeds stored as CSV files.

## Build and run

```bash
cargo build --release --locked
./target/release/hospital_analytics --input-dir /app/data --output /app/output/analytics_report.json
```

## Documentation

| Document | Purpose |
| --- | --- |
| [architecture.md](architecture.md) | Module layout and data flow |
| [data_contract.md](data_contract.md) | Input schemas and output JSON contract |
| [processing_rules.md](processing_rules.md) | Event ordering and business rules |
| [edge_cases.md](edge_cases.md) | Representative scenarios in the sample feeds |

Sample inputs live under `data/`. The census snapshot timestamp (`as_of`) is
declared in `data/README.md`.

## Output

The tool writes a single JSON report containing summary metrics, per-patient
rows, ward occupancy at `as_of`, and rejected events with documented reasons.
