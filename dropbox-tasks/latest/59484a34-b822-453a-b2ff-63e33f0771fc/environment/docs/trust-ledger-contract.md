# Trusted CT ledger contract

Publish reads disposition_matrix.json and the Merkle snapshot path from --snapshot. It writes published_ct_ledger.json.

Fields:

- bundle_id from disposition report
- trusted_serials sorted lexicographically
- needs_review_serials sorted lexicographically
- trusted_count equals len(trusted_serials)
- combined_digest is SHA-256 hex of UTF-8 sorted trusted serials pipe-joined, then pipe, then merkle_row_digest from the snapshot (see /app/docs/publish-seal-lineage.md)
- publish_epoch is the monotonic counter after this publish completes

Publish must not re-read certificate files under certificates/.
