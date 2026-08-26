# Your bench monitor uses `/app/repo/bin/trace_blur` to smooth one-dimensional sen

- **UUID:** `672a9479-ea08-4c08-8535-78efedb7d7c2`
- **Slug:** `your-bench-monitor-uses-app-repo-bin-trace-blur-to-smooth-on`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

Your bench monitor uses `/app/repo/bin/trace_blur` to smooth one-dimensional sensor traces before thresholding. The program reads one JSON file argument with top-level shape `{"inputs":[...]}`.

Each input record has `signal` and `sigma`, with optional `mode` and `truncate`. It must print `{"results":[...]}`, keep the input order, and put one `filtered` array in each result with one value per input sample.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
