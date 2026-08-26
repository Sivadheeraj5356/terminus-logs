# Chronicle artifact paths (v1)

| Path | Wire schema / field index |
| --- | --- |
| /app/state/dsc-peak-capture.json | /app/spec/dsc-peak-capture.schema.json · CAPTURE_TOP_KEYS |
| /app/state/torque-residual-snapshot.json | /app/spec/torque-residual-snapshot.schema.json · RESIDUAL_TOP_KEYS |
| /app/state/hold-spine-ledger.json | /app/docs/hold-spine-ledger.md · HOLD_SPINE_TOP_KEYS |
| /app/state/cross-batch-concordance.json | /app/docs/cross-batch-concordance.md · CONCORDANCE_TOP_KEYS |
| /app/state/polymorph-walk-seal.json | /app/spec/polymorph-walk-seal.schema.json · SEAL_TOP_KEYS (ten-field phase_seal) |
| /app/state/chronicle-bind-manifest.json | /app/spec/b6lc_schema_index.py MANIFEST_KEYS |
| /app/output/lattice-chronicle-report.json | /app/docs/lattice-chronicle-schema.md · ATLAS_REPORT_KEYS |

Authoritative field index: /app/spec/b6lc_schema_index.py  
Residual rounding and asymmetric emit trust: /app/docs/walk-seal-bind.md
