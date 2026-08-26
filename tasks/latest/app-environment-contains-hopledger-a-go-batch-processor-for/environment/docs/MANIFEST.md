# Manifest contract

A manifest is JSON:

```json
{
  "schema_version": 3,
  "checkpoint_dir": "checkpoints",
  "policy": "policy.json",
  "journal": "journal.ndjson",
  "lanes": [
    {"name": "north", "path": "lanes/north.ndjson", "priority": 1},
    {"name": "south", "path": "lanes/south.ndjson", "priority": 2}
  ]
}
```

Rules:

- Relative paths resolve from the manifest directory.
- When `lanes` is present it takes precedence over `journal`.
- Single-journal mode uses lane name `""`, lane priority `0`, and source `"main"` unless a record provides `source`.

CLI:

```bash
hopledger run --manifest PATH --report PATH --digest PATH --audit PATH [--resume-tag TAG]
```

The implementation must create missing parent directories for all requested outputs.

On any failed run, delete the report, digest, and audit paths requested for that invocation.
