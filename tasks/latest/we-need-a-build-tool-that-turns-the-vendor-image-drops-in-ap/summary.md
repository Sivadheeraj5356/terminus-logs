# We need a build tool that turns the vendor image drops in /app/assets/src into t

- **UUID:** `d66c4a28-bb7a-4bf0-a67f-3786324495f2`
- **Slug:** `we-need-a-build-tool-that-turns-the-vendor-image-drops-in-ap`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

We need a build tool that turns the vendor image drops in /app/assets/src into the exact derivatives our CDN expects. Every rule for this — target sizes per asset class, when to crop versus fit, how to normalize camera orientation, the color profile policy, the output naming, and the manifest layout — is written up in /app/spec/asset_processing_spec.md.

Please read the whole thing; the rules differ by asset class and some only appear once, in prose rather than a table. Each source file's asset class comes from /app/assets/src/manifest_inputs.csv.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
