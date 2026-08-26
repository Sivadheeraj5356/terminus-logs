# Crash-recoverable LMDB telemetry replay cache

Repair the C telemetry replayer under `/app`. A recent persistence integration caused replay results to diverge between fresh, resumed, forced, and concurrent executions. Restore the documented behavior while preserving the native C/LMDB architecture and the existing command-line interface.

The behavioral contract is distributed across the visible files under `/app/docs`. Treat those documents as authoritative and reconcile them with the implementation rather than assuming any one source file contains the complete defect. Do not modify tests, seed data, or the matrix driver. Rebuild with `bash /app/scripts/build.sh` and exercise the program through the CLI or `bash /app/scripts/run_matrix.sh`.

The CLI remains:

```bash
/app/bin/telreplay --db PATH --scenario ID --loops N \
  [--state-dir DIR] [--output PATH] [--no-resume]
```

Default state is `/app/state`; default single-report output is `/app/output/.single_report.json`. Every scenario has an independent append-only journal and advisory lock. On startup, scan and validate records, recover from any invalid tail by truncating to the last valid boundary, compute the documented content fingerprint, and either reuse the matching latest snapshot or perform live LMDB replay and append the next durable generation. `--no-resume` forces live replay but does not bypass recovery.

A correct solution must preserve lossless unsigned 64-bit PIDs, honor runtime TOML changes without rebuilding, invalidate snapshots after LMDB content changes or loop-count changes, keep direct and matrix reports canonical, maintain stable descriptor counts, and serialize concurrent cold starts so only one generation is committed. Static JSON, test-specific literals, Python replacement of the C binary, and disabling persistence are invalid.
