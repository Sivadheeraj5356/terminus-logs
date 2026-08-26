# The Rust library at /app/src/src/ is split across nine per-concern

- **UUID:** `c80d568a-892a-4b6f-a60e-b317c48413fe`
- **Slug:** `the-rust-library-at-app-src-src-is-split-across-nine-per-con`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

The Rust library at /app/src/src/ is split across nine per-concern modules — `fibonacci`, `zeckendorf`, `fibonacci_code`, `elias_gamma`, `primes`, `bracket`, `wythoff`, `negafibonacci`, `pisano`. Each ships with unimplemented bodies; lib.rs only re-exports.

Replace every stub so the batch driver produces the expected /app/src/results.json. The algorithmic contract lives under /app/src/docs/contracts/: `decomposition.md`, `canonical.md`, `zeckendorf.md`, `prefix_code.md`, `variants.md`, `roundtrip.md`, `bracket.md`, `codeword.md`, `wythoff.md`, `witnesses.md`, `policy.md`, `rejections.md`, `negafibonacci.md`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
