# Partial Observability Notes

## Surface disagreements

The binary fixtures and text exports represent the same logical records but
were produced by different toolchains.  Some fields will appear to agree when
inspecting a single surface; the disagreements only become visible when both
surfaces are compared side-by-side.

Known areas of potential surface disagreement in the shipped fixtures:

- Numeric fields whose byte positions differ between toolchains.
- Status information that one surface stores raw and the other normalises.

## Malformed-input categories

The `bad/` directory contains fixtures that exercise error handling rather
than canonical conversion.  Each category corresponds to a `kind` value in
the `error_classification` section of the output bundle:

| Category          | Description                                               |
|-------------------|-----------------------------------------------------------|
| `truncated_header`| Buffer shorter than the minimum record size (12 bytes)    |
| `invalid_checksum`| Stored checksum word does not match the recomputed value  |
| `overflow_field`  | `datum_len` exceeds 0x0FFFFFFF                            |
| `reserved_bit_set`| High nibble of the status byte is non-zero                |
| `unknown`         | Any other unrecognised structural issue                   |

A record matching any of the above categories **must** be reported in
`error_classification` and its `compatibility_trace` entry **must** have
`state = "malformed"`.  It must not be silently normalised and emitted as a
compatible record.

## False-green intermediate states

An earlier run may produce a bundle that looks plausible but is not correct:

- The `interim/stub.json` file is an example of a partially-consistent
  intermediate snapshot.  It covers a subset of records with apparently
  correct fields, while the full bundle still fails.
- Single-group inspection (using `--group set_a` alone) can show locally
  consistent results while the combined `--all-samples` run still detects
  cross-group failures.

The graded artifact is always the terminal bundle from the full
`--all-samples` run.  Intermediate snapshots and single-group outputs are
for debugging only.

## Recovery

Run `clear_scratch.sh` to remove build artifacts and intermediate
files before rebuilding.
