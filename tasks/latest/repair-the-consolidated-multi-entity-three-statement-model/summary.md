# # Repair the consolidated multi-entity three-statement model

- **UUID:** `009e26d2-760a-43f7-8d97-903caf8d35b2`
- **Slug:** `repair-the-consolidated-multi-entity-three-statement-model`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

The Go program in `/app/main.go` reads a manifest JSON path from `os.Args[1]`, joins the three documents it references (`group`, `entities`, `intercompany`), projects the three financial statements for every entity in the group, computes coverage covenants, and consolidates the group. The model is mostly built but does not tie out.

Fix the model code only, keeping the same command-line interface and the existing JSON documents, sections, and field names. The accounting rules the model must follow — how the documents join by entity id and period, the integer arithmetic conventions, the per-entity income-statement, tax, working-capital, equity, and circular debt/interest logic, the coverage covenants, and the consolidation with intercompany eliminations and minority interest — are documented in `/app/MODEL_SPEC.md`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
