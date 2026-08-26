# Bundle format

A bundle is a single JSON object. Every numeric field is an integer. There are
no floating point values anywhere in the format.

```json
{
  "unit": 1000,
  "bins": 10,
  "cells": 8,
  "lanes": 2,
  "fit": [ {"raw": 640, "hit": 1, "lane": 0}, ... ],
  "rim": [ {"raw": 120, "hit": 0, "lane": 1}, ... ],
  "hold": [ {"raw": 500, "hit": 1, "lane": 0}, ... ],
  "rungs": [
    {"severity": 0, "budget": 42, "span": 2, "rows": [ {"raw": 610, "hit": 0, "lane": 1}, ... ]},
    ...
  ]
}
```

## Top-level fields

| field   | meaning |
|---------|---------|
| `unit`  | the fixed-point scale. A raw score or a mapped value of `unit` means 1.0, `0` means 0.0. Must be positive. |
| `bins`  | the number of equal-mass bins used when measuring a rung. Must be positive. |
| `cells` | the number of equal-width cells used by the `hist` family. Must be positive. |
| `lanes` | the number of groups. Every `lane` index must be in `[0, lanes)`. Must be positive. |
| `fit`   | the fit fold: the rows every family is fitted on. Must be non-empty. |
| `rim`   | optional edge-placement rows. May be empty or omitted (treated as empty). Rim rows never take part in fitting a map. They take part only when placing equal-mass edges under `/app/environment/docs/contract.rst` section 3. |
| `hold`  | holdout fold used only for the emitted holdout witness. Must be non-empty. Hold rows never take part in fitting a map or placing edges. |
| `rungs` | the ladder, listed in strictly ascending `severity` order. |

## Row

| field  | meaning |
|--------|---------|
| `raw`  | the uncalibrated score, an integer in `[0, unit]`. |
| `hit`  | the observed label, exactly `0` or `1`. |
| `lane` | the group index, an integer in `[0, lanes)`. |

## Rung

| field      | meaning |
|------------|---------|
| `severity` | the shift stage. Strictly ascending across `rungs`. |
| `budget`   | the per-rung bound, in the same `unit` scale. See `/app/environment/docs/contract.rst`. |
| `span`     | maximum allowed strength increase from the previous rung, in `{0, 1, 2}`. Ignored on the first rung. When the field is omitted, the value is `2`. See `/app/environment/docs/contract.rst` section 7. |
| `rows`     | the rung's observations. Must be non-empty. |

## Rejected bundles

A bundle is malformed, and `/app/bin/plangen plan` exits non-zero without writing
a document, when any of the following hold:

- `unit`, `bins`, `cells`, or `lanes` is not positive
- `fit` is empty, `hold` is empty, or any rung has no `rows`
- any `raw` is outside `[0, unit]` (including rim and hold rows)
- any `hit` is not `0` or `1` (including rim and hold rows)
- any `lane` is outside `[0, lanes)` (including rim and hold rows)
- any rung `span` is outside `{0, 1, 2}`
- `rungs` is not in strictly ascending `severity` order

A malformed bundle is rejected before any document is written.

## Immutability

`plangen` never writes to the bundle path. The bundle is read-only input and is
byte-identical after any number of runs.

## Examples

Three bundles ship under `/app/environment/data/bundles/`:
`/app/environment/data/bundles/compact.json`,
`/app/environment/data/bundles/wide.json`, and
`/app/environment/data/bundles/steep.json`. They are format examples. They are
smaller than the ladders the tool is expected to handle and they are not a
statement about which family any rung should use.
