# cryoready CLI

Binary: `/app/bin/cryoready`

## inventory

```
cryoready inventory --facility <path> --catalog <path> --maintenance <path>
```

Loads the three inputs, evaluates per-vessel metrics, and writes the durable staging document to `$CRYOREADY_STATE_DIR/inventory-stage.json` (default state dir `/app/state`). Records an inventory run in the ledger.

## assess

```
cryoready assess --facility <path> --catalog <path> --maintenance <path> --output-report <path> --output-certificate <path>
```

Requires a current inventory stage. If the stage is missing, exit status is 2 and stderr mentions `inventory`. If the stage digests do not match the current input files, exit status is 2 and stderr mentions `inventory` (stale stage). On success, writes the readiness report and certificate JSON files and records an assess run in the ledger.

## Environment overrides

- `CRYOREADY_STATE_DIR` — absolute directory for `inventory-stage.json`
- `CRYOREADY_LEDGER_PATH` — absolute path for the durable ledger JSON
