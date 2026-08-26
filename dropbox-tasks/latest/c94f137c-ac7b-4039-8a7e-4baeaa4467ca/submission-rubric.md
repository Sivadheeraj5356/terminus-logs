# Submission rubric — go-claim-docket-seal-audit

Paste these lines into the submission UI. Each criterion uses positive wording; penalties use ASCII hyphen-minus negative scores.

Agent reads `/app/environment/docs/tally_rules.md`, `checkpoint_contract.md`, `ledger_contract.md`, or `wire_layout.md` before editing ingest, checkpoint, digest, ledger, or report sources, +2

Agent repairs Castagnoli CRC-32C validation over CDKT frame bytes so bad checksums increment `crc_failure_count` and surviving totals exclude failed frames, +5

Agent walks `*.cdk` shards in ascending basename order and filters frames to the requested audit epoch before chain and settlement processing, +3

Agent applies matching `{dir_basename}.cdkmark` checkpoint sidecars so `chain_tail_sha256` seeds the rolling digest, `skip_through_seq` omits prefix frames from both the chain walk and all output tallies including `anchor_skip_count`, and stale fingerprint or epoch mismatches ignore the sidecar, +5

Agent implements sequence-aware rolling SHA-256 chain links using profile `chain_seq_width` fixed-width decimal **wire header seq** tokens, canonical JSON per ledger contract (slim tombstone keys), and global read order across sorted shards, +5

Agent repairs ledger settlement so tombstones clear prior upsert/transfer rows without incrementing `retract_count`, `replaces_seq` supersedes the earlier slot, duplicate account+seq slots increment `duplicate_slot_drops`, and `void` rows increment `retract_count` while all included kinds stay in the chain walk, +5

Agent enforces the region gate from `/app/environment/configs/audit_profile.json` and `/app/environment/data/region_codes.txt` so foreign-region upsert/transfer rows are chained, excluded from `record_count` and `distinct_account_count`, and counted in `region_reject_count`, +3

Agent derives `transfer_amount_sum`, `min_seq`, and `max_seq` from the same checkpoint-filtered kept stream that feeds the chain walk and settlement, +3

Agent keys persisted run tail state by docket fingerprint and epoch so unrelated directories and poisoned tails cannot seed chain recomputation, +3

Agent emits the flat report object at `/app/out/claim_docket_audit.json` with contract fields and no debug wrapper envelope, +3

Agent rebuilds claimdocketaudit after source edits and reruns audit on practice and regression fixture directories to regenerate output, +3

Agent hand-writes `/app/out/claim_docket_audit.json` without rebuilding claimdocketaudit and rerunning audit, -5

Agent edits practice or regression fixture bytes instead of fixing Go sources under `/app/environment`, -3

Agent patches JSON shaping or wraps the report while framing, checkpoint, chain, or ledger logic remains broken, -3

Agent seeds the chain from a persisted run tail or applies checkpoint skip only to the chain walk while settlement still counts skipped prefix frames, -3

Agent includes CRC-failed frames in the chain walk or settlement totals instead of counting them only in `crc_failure_count`, -3

Agent reports `transfer_amount_sum` from raw frame sums or leaves `anchor_skip_count` at zero while checkpoint sidecars are active, -3

Agent changes verifier expectations or shell harness files instead of repairing claim docket audit semantics under `/app/environment`, -5
