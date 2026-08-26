# The formal language in /app represents one arithmetic expression over IEEE 754 d

- **UUID:** `595e7c67-ccaf-4544-8f5b-458174baba9b`
- **Slug:** `the-formal-language-in-app-represents-one-arithmetic-express`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

The formal language in /app represents one arithmetic expression over IEEE 754 double precision values. Its expressions contain number literals, the spellings inf and nan, free variables, unary minus, parentheses, and the binary operators plus, minus, times, and divide.

The required artifact is a deterministic expression reducer that reads one program and emits the equivalent reduced program. The accepted syntax is defined by /app/docs/grammar.md, while /app/docs/semantics.md defines evaluation, permitted reductions, and canonical numeric rendering.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
