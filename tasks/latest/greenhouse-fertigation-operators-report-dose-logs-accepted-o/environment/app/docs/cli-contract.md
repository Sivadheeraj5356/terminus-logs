# CLI contract

## fert-ingest

fert-ingest --events path [--db /app/data/fertigation.db] [--profile /app/config/greenhouse-profile.json]

- Applies migrations, ingests one JSONL file in one transaction (when fixed).
- Exit 0 on success; non-zero on validation or DB errors.
- Environment FERT_DB used when --db omitted.
- Parses lines in ascending event_seq order (not physical file order).
- On any error after the transaction starts, roll back all rows from that ingest invocation.

### fert-ingest stderr strings

On non-zero exit, fert-ingest writes a one-line message to stderr. Tests match these substrings case-insensitively:

| Condition | stderr substring |
|-----------|------------------|
| line_crc does not match canonical CRC-16/CCITT-FALSE body | line_crc mismatch |
| BATCH_OPEN zone_id not listed in profile zone_ids, or zone not registered | unknown zone |
| BATCH_OPEN while zone already has an OPEN batch | batch busy |
| DOSE_TICK recorded_at_unix not strictly after prior dose on same batch | non-increasing recorded_at |
| BATCH_CLOSE when dose_events count for batch is below profile min_dose_count | insufficient doses |

## fert-export

fert-export [--db /app/data/fertigation.db] [--profile /app/config/greenhouse-profile.json] [--out /app/output/fertigation-compliance.json]

- Writes compliance JSON for all CLOSED batches only.
- Exit 0 on success; non-zero on DB or profile errors.

Build both binaries with /app/scripts/build.sh (requires CGO_ENABLED=1).
