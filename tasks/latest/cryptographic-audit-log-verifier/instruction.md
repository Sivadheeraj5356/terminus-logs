# Cryptographic Audit Log Verifier

A cryptographic audit log validation pipeline lives under `/app/src/`. The verifier reads append-only log chains stored in segment files and produces a deterministic JSON validation report. The implementation is split across cooperating modules, but multiple independent defects remain. Diagnose and repair the pipeline so that it validates arbitrary audit logs correctly.

The reference dataset under `/app/data/` is a valid exemplar. Cryptographic bindings between records, segment Merkle roots, and the manifest signature are internally consistent throughout that dataset. Use the exemplar and `/app/spec.md` as ground truth, and recompute every digest independently.

The starter implementation is defective: running it against the reference dataset will incorrectly report violations even though the data is sound. Repair the modules involved in loading, hashing, Merkle construction, cross-segment state, timestamp comparison, and manifest binding.

## CLI Interface

```bash
/app/src/audit_verify.py --data-dir <PATH> --report <PATH>
```

- `--data-dir`: Directory containing `manifest.json` and segment files.
- `--report`: Path where the output validation JSON report is written.

## Output Report

Write JSON to `--report`:

```json
{
  "valid": false,
  "summary": {
    "segments_checked": 2,
    "records_checked": 5,
    "error_count": 1
  },
  "errors": [
    {
      "type": "tampered_record",
      "segment_id": "segment_0",
      "event_id": "evt_102",
      "details": "Hash mismatch: recomputed ... does not match record_hash ..."
    }
  ]
}
```

- `valid`: `true` only when `errors` is empty.
- Sort `errors` deterministically by `segment_id`, then `event_id`, then `type` (ascending; nulls last).

## Requirements

- Process segments strictly in manifest order and treat the full run as one contiguous chain.
- Recompute every digest from canonical inputs; never trust stored hashes or roots.
- Accumulate all applicable failures in one deterministic report.
- Timestamps may be numeric epochs or ISO-8601 strings; compare mixed forms by normalized UTC epoch seconds, allowing equal instants.
- When a segment file is missing, report `missing_segment` and skip manifest signature verification.

See `/app/spec.md` for the full invariant table, schema details, canonical preimage formats, Merkle rules, manifest binding, and timestamp normalization requirements.
