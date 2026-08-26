The workspace at /app/ops holds the exported service logs after the service was rotated, reloaded, rolled back in one partition window, and exported again. Reconcile the operational authorities so export --root /app/ops --out /app/output/current produces a signed compliance bundle whose report reflects the final partition set, cursor lineage, and omission ledger.

Read /app/environment/docs/contract.md, cursor_trace.md, ledger.md, manifest.md, and commands.md. They cover the event trace, SQLite checkpoint columns, manifest fields, digest formulas, acceptable terminal states, legacy v1 compatibility, and the export/verify commands.

The authorities to reconcile are /app/ops/runtime/cursor_trace.jsonl, /app/ops/logs/*.journal, /app/ops/state/export_ledger.sqlite, /app/ops/state/export_state.json, and /app/ops/manifests/bundle_manifest.json.

Use /app/ops as the durable work surface. Static writes under /app/output are not enough; the bundle must be regenerated from these authorities. Preserve the legacy v1 bundle under /app/ops/legacy.
