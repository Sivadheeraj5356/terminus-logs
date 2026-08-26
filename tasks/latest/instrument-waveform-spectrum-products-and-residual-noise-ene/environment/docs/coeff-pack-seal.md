# Coefficient pack seal

## /app/state/coeff-pack.json

Written by decompose-threshold together with the inspectable ledger. This pack is the authoritative coefficient artifact for reconstruct-export.

Required fields:

- `schema_version` = 2
- `snapshot_digest`: lowercase hex SHA-256 of the canonical snapshot payload described below
- `policy_revision_id`: must equal the snapshot winner
- `mad_multiplier`: must equal the snapshot multiplier (12-decimal rounded)
- `effective_levels`: global max per-trace clamp across the run
- `pack_seal`: lowercase hex SHA-256 binding described below
- `entries`: same ordered coefficient entries as the ledger (sorted by `trace_id`)

## Snapshot digest

Hash the JSON object with keys in this exact order:

`case_id`, `mad_multiplier`, `max_levels`, `policy_revision_id`, `requested_levels`, `schema_version`, `traces`

Values are taken from the live `/app/state/trace-snapshot.json`. Nested `traces` keep their staged order and fields. Digest bytes are SHA-256 of the UTF-8 JSON serialization of that object, encoded as lowercase hex.

## Pack seal

Hash the following UTF-8 concatenation (no JSON wrapping):

1. `snapshot_digest`
2. literal `|`
3. decimal `policy_revision_id`
4. literal `|`
5. for each entry in `entries` order (`trace_id` ascending):
   - `trace_id`
   - `|`
   - decimal `original_length`
   - `|`
   - decimal `effective_levels`
   - `|`
   - each `pad_lengths` value as decimal followed by `,`
   - `|`
   - each approximation sample formatted with 12 decimal places followed by `,`
   - `|`
   - for each detail band in index order: each sample formatted with 12 decimal places followed by `,`, then band terminator `;`
   - entry terminator `#`

Encode the SHA-256 digest as lowercase hex into `pack_seal`.

## Export binding

reconstruct-export must:

1. load `/app/state/coeff-pack.json`
2. recompute `snapshot_digest` from the live snapshot and require an exact match
3. require `policy_revision_id` and `mad_multiplier` to match the live snapshot
4. recompute `pack_seal` and require an exact match
5. invert Haar using pack `entries` only

If any check fails, exit non-zero and write no outputs. The ledger remains an inspectable summary and must not be treated as an alternate unsealed reconstruction source. reconstruct-export must not recompute Haar coefficients from `/app/data/traces/`.

## Stale stage rejection

If the snapshot is rewritten after decompose-threshold without regenerating the pack (for example a changed `policy_revision_id` or `mad_multiplier`), reconstruct-export must reject the stale pack.
