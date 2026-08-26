# Our Ruby quantization lab under `/app/environment` calibrates activation tensors

- **UUID:** `a36f4d17-6dc8-4905-bcd8-78178bd1a0af`
- **Slug:** `our-ruby-quantization-lab-under-app-environment-calibrates-a`
- **Category:** machine-learning
- **Difficulty:** hard

## Summary

Our Ruby quantization lab under `/app/environment` calibrates activation tensors into exportable scale buckets for offline inference bundles. After the last ops refresh, scale rows for `sage` look right in the staging report, but the terminal ledger from the matrix driver disagrees on row digests between live batch accumulation and replayed checkpoint bytes for the same seeded inputs.

The built-in calibration profile ids are exactly `fp16_baseline`, `int8_strict`, and `mixed_edge`; do not rename them or substitute case ids as mode ids. Per-profile activation statistics must never bleed across incompatible profiles named in `/app/environment/docs/qcl_contract.md`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
