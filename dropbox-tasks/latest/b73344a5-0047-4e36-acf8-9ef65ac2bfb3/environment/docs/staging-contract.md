# Staging contract

## /app/state/trace-snapshot.json

Written by ingest-traces only.

- `schema_version` = 1
- `case_id`
- `policy_revision_id` active winner
- `mad_multiplier` from the winning policy
- `requested_levels`, `max_levels` from denoise-config.json
- `traces`: `{trace_id, sample_rate_hz, samples}` sorted by `trace_id`
- Floats rounded to 12 decimal places

## /app/state/coeff-ledger.json

Written by decompose-threshold. Consumes the snapshot only. Inspectable summary of thresholded coefficients.

- `schema_version` = 1
- `policy_revision_id`
- `effective_levels`
- `entries`: per trace `{trace_id, original_length, effective_levels, approx, details, pad_lengths}`
  - `approx`: coarsest approximation vector `AL`
  - `details`: array length `effective_levels` where index 0 is finest `D1` and the last index is coarsest detail `DL`
  - `pad_lengths`: pre-pad lengths recorded at each forward level (index 0 = finest level), used by inverse trim
- Soft-thresholded detail values are stored; approximation is unthresholded

## /app/state/coeff-pack.json

Authoritative sealed coefficient artifact written by decompose-threshold. Schema, digest, and seal rules are defined in /app/docs/coeff-pack-seal.md. reconstruct-export must consume and verify this pack; the ledger alone is not sufficient.

## /app/state/threshold-journal.json

Written by decompose-threshold alongside the ledger and pack.

- `schema_version` = 1
- `policy_revision_id`
- `mad_multiplier`
- `mad_sigma` (global: median over concatenated finest-detail absolute values across traces, then `/ 0.6745`)
- `lambda0`
- `lambdas`: array of per-level `lambda_j` for `j = 1 .. L` (index 0 = finest)
- `detail_coeff_count`
- `thresholded_zero_count` (detail coeffs driven exactly to zero)

## Export rule

reconstruct-export must verify /app/state/coeff-pack.json against the live snapshot per /app/docs/coeff-pack-seal.md, invert from pack entries, and read the journal for audit metadata. It must not recompute Haar coefficients from `/app/data/traces/` and must not accept an unbound ledger when the pack seal fails.
