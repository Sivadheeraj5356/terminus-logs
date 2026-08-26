# Rotlog export contract

The workspace under `/app/ops` is an operator-owned snapshot for one service-log export. The authoritative final state is derived by joining four records: the cursor event trace, the rotated partition files, the SQLite checkpoint ledger, and the bundle manifest. The export is complete only when every partition event in the cursor trace has one matching ledger row and one matching manifest entry. Events with `action = export` are copied into the bundle; events with `action = omit` stay out of the copied partition set but remain in both the manifest and the ledger with an omission digest.

A terminal export state uses `schema_version = 2`, `status = complete`, `last_complete_event_seq` equal to the last partition-bearing cursor event, `succeeded_after_partition` equal to the last exported partition, `high_water_cursor` equal to that partition's `cursor_end`, `lineage` containing exported partitions in cursor order, and `omitted_partitions` containing omitted partitions in cursor order. The export command may be repeated after `/app/output` is removed and must regenerate identical report semantics from the authorities.

Legacy bundle v1 has no omission rows. It remains acceptable only when its exported partition cursor chain is monotonic and every digest still matches the partition bytes.

## Current fixture terminal values
For this fixture, the terminal high-water cursor is `s=32;b=boot-b`. The final exported partition list is `part-0001`, `part-0002`, and `part-0004`; `part-0003` is the single omitted rollback-superseded partition. A complete report must set `status` to `complete`, keep `authority_mismatches` empty, publish `exported_partitions` and `omitted_partitions` arrays, and include the complete `partitions` array derived from the cursor trace. The report and signed manifest use SHA-256 (`sha256`) digests for file bytes, omission records, manifest entries, lineage hashes, and signatures.
