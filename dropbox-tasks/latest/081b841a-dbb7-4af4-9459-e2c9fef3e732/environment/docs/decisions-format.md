# Decisions report

`data.orchid.ledger.report` is the bundle's only exported document. The audit
pipeline writes it to `/app/out/decisions.json`.

```json
{
  "generation": 47,
  "decisions": [
    {
      "name": "express",
      "ecosystem": "npm",
      "version": "4.19.2",
      "decision": "approve",
      "reasons": [],
      "annotations": []
    }
  ]
}
```

Contract:

- `generation` echoes the input's ledger generation.
- `decisions` carries exactly one entry per input dependency, ordered by
  `ecosystem`, then `name`, then `version` (plain string comparison, ascending).
- `decision` is `"reject"` when `reasons` is non-empty, `"annotate"` when
  `reasons` is empty and `annotations` is non-empty, and `"approve"` when both
  are empty.
- `reasons` and `annotations` are sorted, duplicate-free arrays of the finding
  identifiers defined in the maintainer handbook (chapter on annotations and
  reason codes). Both arrays are always present.
- The reason and annotation vocabulary, and the conditions that produce each
  entry, are governed by `/app/docs/handbook/` — the handbook is authoritative
  when this file and the policy disagree.
