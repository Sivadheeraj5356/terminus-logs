# Valuation snapshot policy

Ledgers may include:

```json
"genealogy_snapshot": {"as_of_year": 1995}
```

When present, clip the rank guild_assignment timeline before any restoration_audit or attestation math:

- Drop dye_reformulations whose `year` is after `as_of_year`.
- Drop export_routes epochs whose `from_year` is after `as_of_year`.
- For remaining epochs, replace `to_year` with `min(to_year, as_of_year)`.

Apply the same clipped dye_reformulations and epochs to both restoration_audit compounding and certificate span coverage for that bundle run. Snapshot bounds do not alter maker lineage compilation, which still uses the rank completion year from the catalog.

## Valuation journal modes

- `TRACE_HALT=1` writes a full computed report to `/app/output/.genealogy_journal.json` and must not write the `--out` path.
- `TRACE_RESUME=1` reads the journal when present and writes the `--out` report; otherwise it performs a full compile.
- A cold compile followed by `TRACE_RESUME=1` must agree with a single cold compile for the same bundle and anchors.
