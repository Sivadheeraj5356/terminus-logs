# A TypeScript program in `/app` fits an isotonic regression to a set of scattered

- **UUID:** `19a22c8e-f990-4380-ae3c-378333f26e4f`
- **Slug:** `a-typescript-program-in-app-fits-an-isotonic-regression-to-a`
- **Category:** machine-learning
- **Difficulty:** hard

## Summary

A TypeScript program in `/app` fits an isotonic regression to a set of scattered points and predicts the fitted response at a list of query positions. It must reproduce `sklearn.isotonic.IsotonicRegression` exactly.

It reads one JSON object from standard input of the form `{"inputs": [ ... ]}` and writes one JSON object to standard output of the form `{"results": [ ...

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
