# The workbook engine under /app should be implemented in Dart only. Put the sourc

- **UUID:** `257d3792-585b-4de0-bb6d-957ba12ad7d0`
- **Slug:** `the-workbook-engine-under-app-should-be-implemented-in-dart`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

The workbook engine under /app should be implemented in Dart only. Put the source under /app/src and make /app/src/main.dart the runnable entrypoint.

The verifier runs it directly as `dart /app/src/main.dart <input-json> <output-dir>`, not through `dart run`. It must work with arbitrary input and output paths, fail nonzero for a missing input file, overwrite stale output files, and write deterministic JSON stage files into the requested output directory.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
