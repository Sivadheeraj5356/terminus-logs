# Audit Log Verifier Specification

This document is the authoritative contract for the validation pipeline under `/app/src/`. The reference dataset in `/app/data/` is a valid exemplar; derive every encoding rule from it and apply uniformly to unseen inputs.

## Input schema

The data directory contains:

- `manifest.json` with an ordered `segments` array (for example `"segment_0.json"`) and a `signature`.
- One segment file per manifest entry. Each segment JSON object contains `segment_id`, `merkle_root`, and `records`.
- Each record contains `event_id`, `timestamp`, `payload`, `previous_hash`, and `record_hash`.

Hash-valued fields must be exactly 64 lowercase hexadecimal characters when well-formed.

## Invariant table

Validate the entire manifest-ordered sequence as a single contiguous chain and report violations with these error types:

| Invariant | Requirement | Error type |
|-----------|-------------|------------|
| Segment presence | Every manifest-listed segment file must exist; invalid JSON is structural | `missing_segment`, `malformed_record` |
| Segment identity | Embedded `segment_id` must match the segment filename stem | `segment_id_mismatch` |
| Record schema | Required fields with correct types; invalid hash encoding | `malformed_record`, `malformed_hash` |
| Record integrity | `record_hash` must match a recomputed digest over the canonical record preimage | `tampered_record` |
| Chain continuity | `previous_hash` links to the preceding record across all segment boundaries; genesis uses 64 zeros | `broken_chain` |
| Segment Merkle root | `merkle_root` must match an independently recomputed tree over the segment's record hashes | `bad_merkle_root` |
| Manifest signature | `signature` must match a recomputed binding over the segment Merkle roots in manifest order | `bad_manifest_signature` |
| Timestamp order | Timestamps are non-decreasing (`>=`) across the full sequence after UTC normalization | `bad_timestamp_order` |
| Event uniqueness | `event_id` is globally unique; report each duplicate occurrence | `duplicate_event_id` |

When multiple invariants fail on the same record, report each violation independently.

## Record preimage

Each `record_hash` is `SHA-256` over UTF-8 bytes of:

```
{event_id}:{timestamp}:{payload}:{previous_hash}
```

- `timestamp` is serialized exactly as it appears in JSON (string or number). Do not normalize timestamps for hashing.
- `previous_hash` of the first record in the entire manifest-ordered chain is 64 ASCII `0` characters.

## Merkle tree

Segment `merkle_root` is built from the segment's `record_hash` leaves in record order:

1. Empty segment: `SHA-256("")`.
2. Odd leaf count at any level: duplicate the unpaired leaf (pair it with itself).
3. Parent node: `SHA-256(left || right)` where `left` and `right` are 64-character hex strings concatenated with no separator.

## Manifest signature

When every manifest-listed segment file is present:

```
signature = SHA-256( root_0 || root_1 || ... || root_n )
```

- Roots are the **recomputed** Merkle roots, in manifest `segments` order (not filesystem sort order).
- Concatenation uses no separator between 64-character root digests.

## Segment identity

Each segment file stem (e.g. `segment_1` from `segment_1.json`) must equal the `segment_id` field inside the JSON object. Mismatch is `segment_id_mismatch`.

## Timestamp ordering

Timestamps are non-decreasing (`>=`) across the full manifest-ordered record stream.

Mixed representations must compare by normalized UTC epoch seconds:

- JSON numbers are epoch seconds.
- ISO-8601 strings ending in `Z` parse as UTC.
- ISO-8601 strings with explicit numeric offsets must be converted to UTC before comparison.
- Naive ISO-8601 strings, if encountered, should be interpreted as UTC.
- Equal normalized instants are allowed even when representations differ (for example `2024-06-20T12:00:00+02:00` and `2024-06-20T10:00:00Z`).

## Global state

These persist across segment boundaries for the entire validation run:

- hash-chain `previous_hash`
- last accepted timestamp
- set of seen `event_id` values

## Error reporting

Report every failed invariant independently. Sort errors by `segment_id`, then `event_id`, then `type` (ascending; JSON `null` fields sort after all strings).

When any segment file is missing, emit `missing_segment` and skip manifest signature verification entirely.

## Output schema

Write JSON to the requested report path using this shape:

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

- `valid` is `true` only when `errors` is empty.
- `summary.segments_checked` counts successfully loaded segment files.
- `summary.records_checked` counts records visited in manifest order.
- `summary.error_count` equals `len(errors)`.
