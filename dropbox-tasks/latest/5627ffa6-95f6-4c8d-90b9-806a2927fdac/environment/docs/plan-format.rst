# Plan document format

`/app/bin/plangen plan --input <bundle.json> --out <plan.json>` writes a single
JSON object to `--out`. Every numeric field is an integer.

```json
{
  "unit": 1000,
  "bins": 10,
  "hold": {"hist": 1200, "iso": 980, "giso": 940},
  "rungs": [
    {
      "severity": 0,
      "family": "hist",
      "strength": 0,
      "deviation": 1180,
      "allowance": 2688,
      "values": [620, 620, 754, ...]
    }
  ]
}
```

## Top level

| field   | meaning |
|---------|---------|
| `unit`  | copied from the bundle. |
| `bins`  | copied from the bundle. |
| `hold`  | holdout witness: each family's sealed-edge deviation on the bundle `hold` rows, per `/app/environment/docs/contract.rst` section 8 item 6. Keys appear in the order `hist`, `iso`, `giso`. |
| `rungs` | one record per bundle rung, in the bundle's ascending `severity` order. |

## Rung record

| field       | meaning |
|-------------|---------|
| `severity`  | the rung's severity, copied from the bundle. |
| `family`    | the chosen family name: `hist`, `iso`, or `giso`. |
| `strength`  | the chosen family's strength: `0`, `1`, or `2`. Must agree with `family`. |
| `deviation` | the chosen family's deviation over this rung, per `/app/environment/docs/contract.rst` section 5. |
| `allowance` | `budget * len(rows)` for this rung, per `/app/environment/docs/contract.rst` section 6. |
| `values`    | the chosen family's fit fold map applied to each of the rung's rows, in the bundle's row order. One entry per row. |

`rungs` has exactly one record per bundle rung and appears in the same order.
`values` has exactly one entry per rung row and appears in the same order.

## Encoding

The document is encoded canonically so that two runs of the same bundle produce
byte-identical files:

- object keys appear in the order given above, not sorted
- indentation is two spaces per level
- the file ends with exactly one trailing newline

## Exit status and failure

| situation | destination | exit |
|-----------|-------------|------|
| accepted assignment found | written | `0` |
| bundle is infeasible (`/app/environment/docs/contract.rst` section 9) | removed if present | non-zero |
| bundle is malformed (`/app/environment/docs/input-format.rst`) | untouched | non-zero |

A non-zero exit never leaves a document that describes the run. On an infeasible
bundle the destination is removed, so a document from an earlier run cannot be
mistaken for a result for this one.

## The document is generated, not authored

The document is a function of the bundle. It is produced by running the built
binary over the bundle. A document that was written by hand, edited after the
fact, or copied from another bundle does not describe the run that produced it,
and re-running the binary over the same bundle overwrites it.
