# Write a Go program, compiled to /app/hmm, that replays and analyses the duration

- **UUID:** `0efd21c1-4598-4c4b-8541-a981d5a3e1cd`
- **Slug:** `write-a-go-program-compiled-to-app-hmm-that-replays-and-anal`
- **Category:** machine-learning
- **Difficulty:** hard

## Summary

Write a Go program, compiled to /app/hmm, that replays and analyses the duration-explicit recording process described by the cases in /app/data/cases.txt. Each case gives model parameters and a 64-bit seed but no recording.

Your program has to produce three things per case, written one case at a time in input order to /app/output/results.txt at full double precision. First the exact recording the reference process emits for that seed, entry for entry.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
