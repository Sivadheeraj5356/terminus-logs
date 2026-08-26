# Subvolume parity tooling under `/app` drifts after operator interruption, retry,

- **UUID:** `7b41e0fc-40f3-440f-b620-d4eabca0cbaa`
- **Slug:** `subvolume-parity-tooling-under-app-drifts-after-operator-int`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

Subvolume parity tooling under `/app` drifts after operator interruption, retry, warm memo reuse, or reload overlays: row stamps, summary folds, and the stream sidecar disagree even when bundled lane fixtures remain valid, and warm memo entries can leave row stamps looking locally coherent while summary folds and stream sidecars still disagree after matrix-all completes. Correct the m6_ctl crate sources under `/app/environment` so the matrix runner regenerates `/app/output/bw_emit.json` and `/app/output/stream_sidecar.bin` through matrix-all; hand-written JSON, cache deletion alone, static output writes, and test edits are insufficient because the verifier rebuilds with `cargo build --release --locked` and reruns matrix-all.

Install the rebuilt CLI at `/app/bin/m6_ctl`, run `m6_ctl matrix-all`, and emit JSON following the bw_emit_v1 layout in `/app/environment/schemas/report_fields.toml` with top-level `rows` and `summary`; the summary `lineage_digest` must agree with the regenerated stream sidecar. Derivations, pass ordering, digest fold ordering, memo semantics, sidecar encoding, and remaining summary fields are in `/app/environment/docs/fc0_contract.md`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
