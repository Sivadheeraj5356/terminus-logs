# Implement a single-pass, bounded-memory online classifier in Java. The stream co

- **UUID:** `22c1b159-31d8-4557-b337-ef0d92e7af23`
- **Slug:** `implement-a-single-pass-bounded-memory-online-classifier-in`
- **Category:** machine-learning
- **Difficulty:** unknown

## Summary

Implement a single-pass, bounded-memory online classifier in Java. The stream contains one-minute household power rows with missing measurement gaps and delayed sub-meter labels.

For each prediction request, your program must emit the probability that the source row's withheld sub-meter share crosses the request threshold, using only state available before any labels released at that same event. Your implementation lives in /app/environment/src/Solver.java and must build offline with javac.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
