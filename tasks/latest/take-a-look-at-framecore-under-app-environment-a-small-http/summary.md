# Take a look at framecore under /app/environment, a small HTTP/2 style transport

- **UUID:** `8579adc2-6377-4c10-a73c-d411a9be05a4`
- **Slug:** `take-a-look-at-framecore-under-app-environment-a-small-http`
- **Category:** security
- **Difficulty:** hard

## Summary

Take a look at framecore under /app/environment, a small HTTP/2 style transport library. Its header memory accounting has drifted: every session tracks how many bytes and how many headers are currently charged against it from its streams, and every stream accumulates its own header block before handing it to the application layer.

Session totals should reflect only what is still outstanding right now, never climb across idle traffic even across a stream's multiple phases, and a flood of minimally sized headers should not slip past the byte accounting cheaply. Streams also need to enforce which phase can follow which: informational phases only come before the one main headers phase, trailers only come last, and an out-of-order request must be turned away without disturbing the stream's current phase or accumulated block.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
