# Schema-version 3 scenario packs

Schema-version 3 packs replace the flat `samples` array with a sparse revisioned timeline plus calibration revisions. Schema-version 2 packs remain valid and follow `/app/docs/contract.md` unchanged.

## Top level

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | integer | Must be **3** |
| `scenarios` | object[] | Scenario objects in evaluation order |

## Scenario object

| Field | Type | Meaning |
|---|---|---|
| `id` | string | Scenario label echoed in output |
| `sample_rate_hz` | number | Finite sampling rate in hertz |
| `frame_len` | integer | Hann frame length `N` (positive) |
| `hop_len` | integer | Frame hop in samples (positive) |
| `detrend` | string | `"none"` or `"mean"` |
| `gap_policy` | string | `"zero_fill"` or `"skip_frame"` |
| `min_frame_quality` | number | Inclusive quality floor in `(0, 1]` |
| `timeline_len` | integer | Dense timeline length after reconstruction (positive) |
| `bands` | object[] | Weighted frequency bands |
| `sample_revisions` | object[] | Ordered sample upsert revisions |
| `calibration_revisions` | object[] | Ordered calibration revisions |

Schema-version 3 scenarios must not include a top-level `samples` array.

## Band object

| Field | Type | Meaning |
|---|---|---|
| `name` | string | Band label |
| `low_hz` | number | Inclusive lower edge |
| `high_hz` | number | Exclusive upper edge |
| `weight` | number | Finite positive band weight |

## Sample revisions

Each entry in `sample_revisions`:

| Field | Type | Meaning |
|---|---|---|
| `revision_id` | string | Stable revision label used in lineage sealing |
| `ops` | object[] | Upserts applied left to right within the revision |

Each sample op:

| Field | Type | Meaning |
|---|---|---|
| `index` | integer | Timeline index in `[0, timeline_len)` |
| `value` | number\|null | Sample amplitude, or `null` to clear the slot |

Replay rules:

1. Allocate a dense timeline of length `timeline_len` filled with `null`.
2. Walk `sample_revisions` in array order.
3. Within each revision, apply `ops` in array order.
4. Later ops overwrite earlier ops at the same index, including clears to `null`.
5. Out-of-range indices make the pack malformed.

## Calibration revisions

Each entry in `calibration_revisions`:

| Field | Type | Meaning |
|---|---|---|
| `revision_id` | string | Stable revision label used in lineage sealing |
| `ops` | object[] | Calibration spans applied left to right |

Each calibration op:

| Field | Type | Meaning |
|---|---|---|
| `start` | integer | Inclusive span start |
| `end` | integer | Exclusive span end |
| `gain` | number | Finite multiplicative gain |
| `offset` | number | Finite additive offset |

Replay rules:

1. Initialize every timeline index with `gain = 1.0` and `offset = 0.0`.
2. Walk `calibration_revisions` in array order, then `ops` within each revision.
3. For every index `i` with `start <= i < end`, replace that index's gain and offset with the op values.
4. Require `0 <= start < end <= timeline_len`; otherwise the pack is malformed.
5. After sample reconstruction, every non-null sample at index `i` becomes `gain[i] * raw[i] + offset[i]`.
6. Null samples stay null after calibration.

## Semantic equivalence

Two schema-version 3 packs are semantically equivalent when, for every scenario in order:

- Framing controls (`sample_rate_hz`, `frame_len`, `hop_len`, `detrend`, `gap_policy`, `min_frame_quality`, `timeline_len`) match.
- Band lists match in order, including weights and edges.
- After revision replay, the calibrated dense timelines are identical sample-for-sample.
- Concatenated `revision_id` sequences for sample and calibration revisions may differ; lineage sealing uses the reconstructed timeline and the ordered revision-id lists actually present in the pack.

Byte-identical reports are required for semantically equivalent packs that also share the same ordered `revision_id` lists. Packs that reconstruct the same timeline through different revision-id sequences produce identical numeric metrics but different `lineage_hex` / digest values.

## Malformed packs

Missing required fields, wrong types, non-positive sizes, non-finite numerics, invalid enums, empty band names, non-positive weights, `min_frame_quality` outside `(0, 1]`, or out-of-range revision indices/spans are malformed. Malformed packs must exit non-zero and must not modify an existing `--out` report or `--checkpoint` file.
