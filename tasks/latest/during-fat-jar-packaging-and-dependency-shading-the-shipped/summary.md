# During fat-jar packaging and dependency shading the shipped package relocation c

- **UUID:** `d2365ecd-5d1c-4f4d-af67-da77d7b3d062`
- **Slug:** `during-fat-jar-packaging-and-dependency-shading-the-shipped`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

During fat-jar packaging and dependency shading the shipped package relocation consistency validator must analyze twenty bundled packaging relocation batches under /app/reloc-batches that model Maven-shade style dependency namespace remaps across jar artifacts and write one packaging CI report to /app/artifacts/relocation_consistency_report.json. Implement EvaluateBatch in /app/reloclogic/evaluate.go using /app/RELOCATION_SPEC.md, /app/REPORT_LAYOUT.md, and /app/reloc-canon/rules.yaml.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
