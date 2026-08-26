# Recovery set output contract

`/app/bin/vault-qualify --vault <path> --output /output/recovery-set` publishes:

```text
/output/recovery-set/objects/<logical-path>
/output/recovery-set/inventory.jsonl
/output/recovery-set/recovery-root.json
/output/recovery-set/audit.dsse.json
```

## inventory.jsonl

One compact JSON object per recovered object, sorted by UTF-8 `logical_path`:

- `logical_path`, `plaintext_size`, `plaintext_sha256`
- `data_key_commitment`, `envelope_version`, `custody_epoch`
- `active_rewrap_transaction_id`, `organizations` (sorted unique org IDs)
- `recovery_status` = `recovered`

## recovery-root.json

- `schema_version`, `policy_id`, `evidence_snapshot_sha256`, `inventory_sha256`
- `object_digests` (ordered plaintext digests)
- `recovery_root` (SHA-256 over canonical binding record)

## audit.dsse.json

Base64 `payload` signs `recovery_root`, `evidence_snapshot_sha256`, and `inventory_sha256` with the appliance audit key under `/app/vault/keys/`.

## Failpoints

Set `VAULT_QUALIFY_FAILPOINT` to `after-object-stage`, `after-inventory-stage`, `after-root-stage`, or `before-audit-commit` for deterministic interruption testing.
