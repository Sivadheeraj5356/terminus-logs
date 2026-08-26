# Packaging probe schema

See `/app/data/catalog/README.md` for the full ledger and claim JSON schema,
field types, local assemble rule, and exact `row_token` / `state_hash` formulas.

The simulator emits `/app/output/ffm_ledger.json` with a top-level `cases` object
and dual path_mode entries per pack. Stage outputs under workdirs feed the rows.
Every `*.json` pack under `data/scenarios/` must appear in `cases`.
