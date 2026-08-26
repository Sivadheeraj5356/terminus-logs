# Durable ledger

Default path `/app/var/cryoready-ledger.json`, overridable with `CRYOREADY_LEDGER_PATH`.

Shape:

```
{
  "write_seq": <int>,
  "entries": {
    "<facility_digest>|<catalog_digest>|<maintenance_digest>": {
      "inventory_runs": <int>,
      "assess_runs": <int>,
      "last_inventory_digest": "<hex>",
      "last_report_digest": "<hex>"
    }
  }
}
```

Rules:

- Composite entry key joins the three input digests with `|`
- Every successful `inventory` increments `inventory_runs` and advances `write_seq` by 1
- Every successful `assess` increments `assess_runs` (even when digests repeat) and advances `write_seq` by 1
- If the ledger file is truncated/corrupt, recover the longest prefix that parses as a JSON object containing an `entries` object; otherwise start empty
