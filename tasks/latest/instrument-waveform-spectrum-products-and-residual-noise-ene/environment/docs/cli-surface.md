# CLI surface

Binary: /app/bin/haar-denoiser

## Modes

- `version` — print `haar-denoiser 0.1.0` and exit 0
- `ingest-traces` — build /app/state/trace-snapshot.json
- `decompose-threshold` — build /app/state/coeff-ledger.json, /app/state/coeff-pack.json, and /app/state/threshold-journal.json from the snapshot
- `reconstruct-export` — verify the sealed coeff pack, then write /app/output/denoised-traces.json and /app/output/noise-audit.json
- no mode argument — run ingest-traces, then decompose-threshold, then reconstruct-export

Unknown modes exit non-zero with an error on stderr.

## Path overrides

- `HAAR_DATA_DIR` replaces /app/data when set to an absolute path
- `HAAR_STATE_DIR` replaces /app/state when set to an absolute path
- `HAAR_OUTPUT_DIR` replaces /app/output when set to an absolute path

Relative override values must be rejected with a non-zero exit.

## Idempotency

A second full pipeline on unchanged inputs must leave all staged and output JSON files byte-identical.
