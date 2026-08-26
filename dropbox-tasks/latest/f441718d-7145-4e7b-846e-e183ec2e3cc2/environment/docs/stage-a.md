# Stage A — Workflow Parser

## Responsibilities

- Parse workflow JSON schema
- Validate required fields (`name`, node `id`)
- Normalize text with Unicode **NFC** and collapsed whitespace
- Lowercase + trim metadata / param keys; sort keys ascending when materializing maps
- Deterministic workflow ID over the **NFC-normalized name**, a single ASCII
  newline (`0x0A`), then the trimmed version string (both sides of the newline
  are required — hashing name alone is incorrect):

```
workflow_id = Truncate16(DomainHash("workflow-id", name + "\n" + version))
```

  `DomainHash` must use the `pipeline.md` separator (`domain + "\n" + payload`).

- Materialize `depends_on` as directed edges `dep → node`
- Deduplicate and sort edges by `(from, to)` ascending
- Canonical workflow digest: `DomainHash("workflow-canon", canonical_json(workflow))`

## Outputs

`state/normalized.json`, `state/workflow_digest.json`
