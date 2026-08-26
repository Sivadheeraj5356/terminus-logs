# # Counter-system safety analyzer

- **UUID:** `9ad85ea2-4fc0-4cfb-893e-0ed39c0fa39e`
- **Slug:** `counter-system-safety-analyzer`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

`/app` contains a Go analyzer for counter systems — the model behind resource pools, work queues, and token schemes. It reads one job as JSON on stdin: a number of counters, rewrite rules that atomically consume and produce counter units, a start state, and a list of cover queries, each asking whether the system can ever hold at least the queried amounts on all counters simultaneously.

It writes one verdict per query as JSON on stdout — a `covered` array of booleans in query order. Verdicts must be exact for reachability at any depth, and the analyzer must decide every conforming job in bounded time — including systems whose counters can grow without limit, where the reachable state space is infinite.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
