# Cluster schedule audit pipeline

Update Go source under `/app/environment` to implement functions marked `// Stub:` in the coordination packages. The discrete-event driver (`/app/environment/internal/pipeline/run.go`), profile loader, fixture catalog, audit writer, metrics helpers, runner shell, bundled profiles, and offline verifier digest helpers are provided. Complete stub packages per `/app/environment/docs/build_obligations.md` so bundled profiles produce `/app/output/schedule_audit.json` matching `/app/environment/docs/schedule_audit_schema.md`. The image is offline (`allow_internet = false`).

Start with `/app/environment/docs/build_obligations.md`, then read `/app/environment/docs/schedule_audit_schema.md`, `/app/environment/docs/graph_layout.md`, and `/app/environment/docs/operations.md`.

Rebuild driver binaries per `/app/environment/docs/build_obligations.md` after source edits and regenerate audits through the normal runner. Hand-written or static JSON is insufficient — prior output is deleted, sources are rebuilt, and the driver is rerun before scoring.

## Core obligations

- **Output exclusivity:** submit-time and publish-time writer semantics for partition rows documented in `schedule_audit_schema.md`.
- **Dependency admission:** ready-set stamping and admission delay when upstream jobs complete.
- **Dispatch width:** per-tick concurrent starts bounded by free node count.
- **Boundary capture and cold reload:** serialize scheduler state at resume boundaries and rebuild live state without reordering or re-claim drift.
- **Visibility epoch:** published outputs become readable on the tick documented when `strict_deps` is enabled.
- **Chain segmentation:** normalize ascending `boundary_ticks` for `checkpoint_chain` run modes.
- **Lane seal binding:** checkpoint runs write `/app/output/scheduler_lane_state.json` with deterministic `seal_digest`.

For every bundled profile and seed, `steady`, `checkpoint_resume`, and `checkpoint_chain` must produce identical job rows, tick snapshots, partition ledger, and all three summary digests (`schedule_fingerprint`, `tick_dispatch_digest`, `ledger_fingerprint`).

`linear_smoke` is the control profile and must complete within documented bounds. Diamond, gradual, fan-in, and cascade_wave profiles must satisfy completion bands, dispatch geometry, ledger visibility rules, and strict dependency tick gaps in `schedule_audit_schema.md`. Profile JSON edits alone are insufficient when stub packages remain incomplete.

```bash
bash /app/environment/tools/runner.sh /app/environment/profiles/default.json /app/output/schedule_audit.json
bash /app/environment/tools/runner.sh <profile.json> /app/output/schedule_audit.json
```

The verifier cross-checks digest recomputation, node accounting, DAG ordering, duration parity with fixtures, checkpoint parity across seeds and chain boundaries, adversarial suite members, and warm-chain marathon spot checks. Do not change the verifier.
