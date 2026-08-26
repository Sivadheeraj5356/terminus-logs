# EmbedServe hardening CLI

PHP inventory hardening pipeline for EmbedServe inference profiles. Extends stub modules under `lib/embedserve/` to query SQLite, parse the operations bundle, run offline `cargo audit` against the tokenizer sidecar, and persist hardened state.

See `docs/harden_contract.md` and `docs/inventory_schema.md`.
