# CLI contract

Binary path: /app/bin/passenger-rebooking-engine

| Subcommand | Behavior |
|------------|----------|
| (no args) | Same as build |
| build | Run stage then export |
| stage | Ingest /app/data/ (or TB3_DATA_DIR), write /app/state/rebooking-snapshot.json and rebooking-ledger.json |
| export | Read snapshot and ledger, write /app/output/rebooking-plan.json and /app/output/passenger-summary.json |
| version | Print passenger-rebooking-engine/1.0.0 |

Environment overrides (absolute paths only):

| Variable | Default | Effect |
|----------|---------|--------|
| TB3_DATA_DIR | /app/data | Input dataset root |
| TB3_STATE_DIR | /app/state | Snapshot directory |
| TB3_OUTPUT_DIR | /app/output | Export output directory |

Exit code 2 when export cannot read snapshot or ledger files, including when stage has not been run.
