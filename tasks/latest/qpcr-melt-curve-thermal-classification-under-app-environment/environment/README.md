# qPCR melt-curve thermal lab

This offline laboratory stack settles melt-curve observations from an append-only
assay journal and classifies measured temperatures against uplink setpoints under
floating-point numeric policy. Go owns journal settlement and thermal
classification. TypeScript owns the certify driver, independent digests, and
atomic publication of the evidence package.

The shipped data under `data/` is a small operational example. Thermal rules,
assay schema, and package fields are documented in `docs/journal_protocol.md`.
