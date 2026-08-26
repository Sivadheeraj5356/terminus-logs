# Ferry operations needs a crew-recovery plan for disrupted sailings before the ne

- **UUID:** `a4dff906-8783-4950-b02d-21cc26de6adc`
- **Slug:** `ferry-operations-needs-a-crew-recovery-plan-for-disrupted-sa`
- **Category:** data-processing
- **Difficulty:** medium

## Summary

Ferry operations needs a crew-recovery plan for disrupted sailings before the next tide cycle closes. Submit one single standalone `.go` file with `package main` source under `/app` or `/tmp`; that file must compile by itself with `/usr/local/go/bin/go build <file>`, must not rely on companion Go files or modules, must accept `<input_dir> <output_dir>`, finish each run within 90 seconds, read the mounted files in `/app/task_file/input_data/`, and write only to `/app/task_file/output_data/`.

The same solver must also handle two copied input directories: in one, `FERRY-0228` becomes a mandatory high-impact sailing for windows 2 through 4 and must be included with no hard-constraint errors and raw `total_score >= 0.780`; in the other, `FERRY-0189`, `FERRY-0203`, `FERRY-0217`, and `FERRY-0221` become mandatory high-impact sailings while vessel-class capacity in windows 3 and 4 is reduced by 2 each, and that stress run must include all four IDs, assign exactly 160 sailings, use all 24 window/base cells, protect at least 3,500,000 passenger-minutes, avoid hard-constraint errors, and reach raw `total_score >= 0.940`. The original-input strict subscore floors below apply only to the original mounted input.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
