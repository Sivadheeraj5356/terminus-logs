# Checkpoint sidecars

A docket directory may include a JSON sidecar named after the directory basename with a .cdkmark suffix.

| Field | Type | Meaning |
|-------|------|---------|
| epoch | integer | Epoch the checkpoint applies to |
| docket_fingerprint | string | Lowercase SHA-256 hex of sorted *.cdk basenames joined by newline |
| skip_through_seq | integer | Frames with seq at or below this value are omitted from processing |
| chain_tail_sha256 | string | 64-character lowercase hex digest after the skipped prefix |

When epoch and docket_fingerprint match the audit request, the rolling digest seeds from chain_tail_sha256 and frames at or below skip_through_seq are not hashed again.

Those skipped frames are also excluded from every output tally — frame_count, record_count, derived sums, min_seq, max_seq, and the rest — not only from the digest walk.

Apply checkpoint skip only after restricting to the target epoch so foreign-epoch frames never affect anchor_skip_count.
