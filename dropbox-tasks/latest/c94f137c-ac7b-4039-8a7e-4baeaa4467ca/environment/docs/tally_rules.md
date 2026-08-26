# Audit report and tally semantics

The audit subcommand writes a single JSON object (not wrapped in a debug envelope). Top-level fields:

- api_version — schema version (currently 1)
- epoch — audited epoch
- docket_files — sorted *.cdk basenames in the directory
- frame_count — epoch-matching frames kept after checkpoint filtering
- record_count, retract_count, distinct_account_count — settlement totals on the kept stream
- chain_root_sha256 — rolling digest after the walk
- crc_failure_count — checksum and truncation failures while reading shards
- anchor_skip_count — epoch-matching frames dropped by an active checkpoint prefix
- duplicate_slot_drops — last-wins replacements for duplicate account+seq slots
- transfer_amount_sum — sum of amount on final active upsert and transfer rows
- min_seq, max_seq — header seq range among kept frames
- region_reject_count — upsert/transfer rows chained but excluded by the region gate

## Practice corpus

fixtures/practice/ uses epoch 7. Shards are read in ascending basename order (alpha.cdk before beta.cdk). Every CRC-valid frame whose header epoch matches the audit epoch participates unless a matching checkpoint sidecar skips it.

## Chain root

Digest state starts at sixty-four ASCII zero digits unless a matching checkpoint sidecar supplies chain_tail_sha256.

For each kept frame in global read order:

1. Build canonical JSON per ledger_contract.md (tombstones use the slim key set).
2. Form a link token from zero-padded decimal header seq (width from chain_seq_width in configs/audit_profile.json, default 16), a colon, and the canonical JSON.
3. Update state to SHA-256 of UTF-8(state + ":" + link_token) expressed as lowercase hex.

Void payloads participate in the digest walk but not in distinct_account_count.

Settlement rules in ledger_contract.md govern record_count, retract_count, and distinct_account_count. anchor_skip_count tracks checkpoint omissions. duplicate_slot_drops and transfer_amount_sum follow the kept stream only.

## Cross-run state

The auditor may write the last digest tail to var/claim_docket_audit_run.json for observability. Each audit still recomputes totals from shard bytes. Persisted tails are keyed by docket fingerprint and epoch so unrelated directories do not share state.

## Regression corpus

fixtures/regression/ holds focused cases, each in its own subdirectory:

- epoch_mismatch — mixes epochs 7 and 8; auditing epoch 7 ignores epoch 8 frames
- crc_noise — one bad checksum frame excluded from all tallies and the digest
- transfer_void — epoch 9 case with separate transfer and void counts
- checkpoint_seed — ships checkpoint_seed.cdkmark that skips through seq 2
- tombstone_retract — tombstone clears a prior upsert from settlement while staying in the chain
- region_excluded — foreign region row is chained but excluded from record totals
- supersede_slot — replaces_seq retires an earlier slot
- stale_checkpoint — sidecar with mismatched docket_fingerprint is ignored
- shard_order — basename order fixes global frame order across shards
- truncated_tail — partial frame at shard end counts as CRC failure and stops that shard scan
- void_after_supersede — supersede followed by void

## CLI

```
claimdocketaudit audit --docket-dir <DIR> --epoch <N> --json-out <PATH>
```

Default practice output path is out/claim_docket_audit.json.
