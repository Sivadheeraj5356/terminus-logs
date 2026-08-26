# Define `func AnalyzeScene` in `/app/engine/solver/resolver.go` — the stub still

- **UUID:** `e4904d46-ffc2-4a2f-ae58-d0bb152c7b3e`
- **Slug:** `define-func-analyzescene-in-app-engine-solver-resolver-go-th`
- **Category:** games
- **Difficulty:** hard

## Summary

Define `func AnalyzeScene` in `/app/engine/solver/resolver.go` — the stub still panics there today. Wire it up so `make build` from `/app` produces `/app/bin/contact-resolver` over 2048 bytes (the verifier greps that file for `func AnalyzeScene`).

The binary must write `/app/results/contact_stability_report.json` (UTF-8, trailing newline, byte-identical across runs). Specs live in `/app/spec/OUTPUT_SCHEMA.md` and `/app/spec/INPUT_FORMAT.md`; thresholds in `/app/rules/contact_policy.yaml`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
