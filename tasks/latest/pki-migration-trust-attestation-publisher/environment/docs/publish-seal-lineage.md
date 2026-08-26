# Publish seal lineage

Attest writes ct_merkle_snapshot.json with a merkle_row_digest field. The digest is SHA-256 hex over UTF-8 comma-joined tokens serial|leaf_index in snapshot row order (same order as ct_logs entries).

Publish reads disposition_matrix.json and the snapshot file named by --snapshot. It must not re-read certificate files.

combined_digest is SHA-256 hex over UTF-8 pipe-joined sorted trusted_serials, a vertical bar, then the merkle_row_digest from the snapshot.

Each successful publish increments publish_epoch starting at 1. The counter persists in /app/state/pki-evidence/publish_epoch.json as {"epoch": N}.

Repeat publish on the same disposition report without re-attesting still bumps publish_epoch.
