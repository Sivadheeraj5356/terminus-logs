# `/app` is the Go source of [CUE](https://cuelang.org), a configuration and

- **UUID:** `a5a8dc20-9355-4f80-9929-23b01e704bff`
- **Slug:** `app-is-the-go-source-of-cue-https-cuelang-org-a-configuratio`
- **Category:** data-processing
- **Difficulty:** medium

## Summary

`/app` is the Go source of [CUE](https://cuelang.org), a configuration and constraint language: it reads configuration source text, unifies the constraints that text declares, and either produces an evaluated result or reports a **conflict** when a value is required to be two incompatible things at once. It builds offline: ``` cd /app && go build ./...

```

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
