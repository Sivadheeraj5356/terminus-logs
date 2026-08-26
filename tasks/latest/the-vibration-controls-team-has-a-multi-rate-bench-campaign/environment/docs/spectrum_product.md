# Source-spectrum product

The destination is one JSON object with exactly the seven keys below. Objects have
exactly the fields listed. Fraction-valued fields use the reduced `{"n","d"}` contract
from `harmonic_coordinates.md`. Lists use the stated ASCII sort and contain no duplicate
identity rows.

## `selected_sources`

One row per selected candidate, sorted by `(tone_id, source_id)`:

`tone_id`, `source_id` (strings); `omega` (JSON integer); `cos`, `sin`, and `energy`
(fractions). `energy = cos^2 + sin^2`.

## `folded_tracks`

One row per selected candidate and capture, sorted by
`(tone_id, source_id, capture_id)`:

`tone_id`, `source_id`, `capture_id` (strings); `sample_rate`, `trigger_quarters`,
`phase_quarters`, `folded_bin`, and `sine_sign` (JSON integers). `phase_quarters` is the
non-negative value from the trigger rule. `sine_sign` is exactly `-1`, `0`, or `1`.

## `sensitivity_values`

One row per selected candidate and probe, sorted by
`(tone_id, source_id, probe_id)`:

`tone_id`, `source_id`, `probe_id` (strings); `real` and `imag` (fractions). These are
the path value before trigger rotation and folding.

## `source_contributions`

One row per selected candidate, capture, and probe, sorted by
`(tone_id, source_id, capture_id, probe_id)`:

`tone_id`, `source_id`, `capture_id`, `probe_id` (strings); `bin` (JSON integer);
`cos` and `sin` (fractions). Coordinates include trigger rotation, path response, and
folding. A collapsed sine coordinate is zero.

## `reconstructed_bins`

One row for every capture/probe/bin from the input, sorted by
`(capture_id, probe_id, bin)`:

`capture_id`, `probe_id` (strings); `bin` (JSON integer); `cos` and `sin` (fractions).
Coordinates are sums of all `source_contributions` having the same capture, probe, and
bin. Empty sums are zero.

## `residual_balance`

One row for every capture/probe/bin, in the same order as `reconstructed_bins`:

`capture_id`, `probe_id` (strings); `bin` (JSON integer); and the objects `observed`,
`predicted`, `error`. Each nested object has exactly the fraction fields `cos` and
`sin`. `observed = measured - expected`, `predicted = reconstructed_bins`, and
`error = observed - predicted`. Every error coordinate is zero for a successful
recovery.

## `recovery_certificate`

An object with exactly:

- `support_size`, `scalar_unknowns`, `scalar_equations`, `matrix_rank` as JSON integers;
- `exact_fit` as the JSON Boolean `true`;
- `support_key` as the selected candidate identities in canonical order.

There are two scalar equations for each capture/probe/bin row, including collapsed sine
rows. `scalar_unknowns = 2 * support_size`; admissibility makes `matrix_rank` equal that
unknown count.
