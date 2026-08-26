# Next comes the extraction step: turn raw input text into a structured report of

- **UUID:** `7afc8597-9a7d-4e4a-bbd6-403ffb37bc69`
- **Slug:** `next-comes-the-extraction-step-turn-raw-input-text-into-a-st`
- **Category:** security
- **Difficulty:** medium

## Summary

Next comes the extraction step: turn raw input text into a structured report of where each pattern occurs. Building on the compiler from before, implement `rsx scan --patterns /app/data/patterns.txt --input <file>` so that after `cd /app && cargo build --release` the binary at `/app/target/release/rsx` reads one pattern per non-empty line of the patterns file, scans the input file with each of them, and extracts all non-overlapping matches using leftmost-longest (POSIX) semantics.

The anchoring rules and the exact match-advancement behaviour (including zero-length matches and how `^`/`$` constrain a match against the whole input) are the ones written in `/app/docs/regex-spec.md`. The transformed output is a single canonical JSON object on stdout, formatted exactly as the spec prescribes: a `patterns` array with one entry per input pattern in file order, each entry carrying the raw pattern text and the matching spans it extracted as `[start, end)` byte offsets in ascending order.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
