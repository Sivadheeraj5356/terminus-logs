# Claim docket audit drift

Replication QA reports the Go claim docket seal auditor under `/app/environment` no longer matches independent recomputation from fixture bytes on practice and regression trees.

Repair sources under `/app/environment` so the normal pipeline regenerates `/app/out/claim_docket_audit.json`. The verifier rebuilds `/app/bin/claimdocketaudit` from sources and reruns audits across fixture directories; hand-written JSON without that pipeline is insufficient. Do not edit `/tests`.

When the pipeline is correct, `/app/out/claim_docket_audit.json` is a single JSON object (not wrapped in a debug envelope) whose fields match the claim docket audit contract: api_version, epoch, docket_files, frame_count, record_count, retract_count, distinct_account_count, chain_root_sha256, crc_failure_count, anchor_skip_count, duplicate_slot_drops, transfer_amount_sum, min_seq, max_seq, and region_reject_count. Practice runs target epoch 7; per-fixture epoch arguments and corpus layout are in `/app/environment/docs/tally_rules.md`.

Contract definitions, merge order, digest walks, settlement rules, checkpoint sidecars, and CLI usage are in `/app/environment/docs/tally_rules.md`, `/app/environment/docs/checkpoint_contract.md`, `/app/environment/docs/ledger_contract.md`, `/app/environment/docs/wire_layout.md`, and `/app/environment/docs/operators.md`.
