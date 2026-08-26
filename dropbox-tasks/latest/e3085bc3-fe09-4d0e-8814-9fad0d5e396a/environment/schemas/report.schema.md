# integrity_report.json

The reconcile pass writes one JSON object to `output/integrity_report.json`.

```
{
  "schema": "integrity/v1",
  "set_id": <string>,
  "aligned": <bool>,
  "jobs": [ <job>, ... ]
}
```

Each `job`:

```
{
  "name": <string>,
  "events": [ <event>, ... ]
}
```

Each `event`:

```
{
  "path": <string>,
  "logged": <bool>,
  "check": "pass" | "fail" | "skip",
  "verdict": "ok" | "bad"
}
```

## aligned

`aligned` is true when digest logging and appraisal reporting are internally
consistent with the tiered policy in `docs/MODEL.md`, including reads whose
`verdict` is `bad` when appraisal correctly fails.

## measure_log.json

```
{
  "set_id": <string>,
  "rows": [
    { "path": <string>, "digest_hex": <string> },
    ...
  ]
}
```

`set_id` must match across `read_traces.json`, `measure_log.json`, and
`integrity_report.json`.

Digest row `path` values use the workload read string as issued. Coverage and
manifest lookup use the canonical path form in `docs/MODEL.md` (duplicate slash
segments and dot segments collapsed).
