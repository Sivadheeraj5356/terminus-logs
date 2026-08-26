# Policy input document

`/app/bin/csv2input.py` converts the ledger fixtures and the OpenSSL hash
report into the single JSON document the Rego bundle evaluates. It is written
to `/app/out/policy_input.json`.

```json
{
  "generation": 47,
  "dependencies": [
    {
      "name": "express",
      "ecosystem": "npm",
      "version": "4.19.2",
      "license": "MIT",
      "channel": "stable",
      "provenance": "verified",
      "lock_generation": 46,
      "scope": "runtime",
      "origin": "direct",
      "install_scripts": false,
      "artifacts": []
    }
  ],
  "hash_report": {
    "registry/<model>/<file>": "<sha256 lowercase hex>"
  },
  "quarantine": [
    {
      "kind": "package",
      "ecosystem": "npm",
      "name": "event-stream-flat",
      "digest": "",
      "status": "active",
      "clause": "QR-2101"
    }
  ]
}
```

- `dependencies[].artifacts` carries `{"path": ..., "digest": ...}` objects for
  model dependencies; the digest is the ledger's pin, not the computed value.
- `hash_report` maps each artifact path found on disk to its computed SHA-256.
  A pinned path with no file on disk is simply absent from the report.
- Field values are copied from the CSVs unchanged, except `lock_generation`
  (integer) and `install_scripts` (boolean).
