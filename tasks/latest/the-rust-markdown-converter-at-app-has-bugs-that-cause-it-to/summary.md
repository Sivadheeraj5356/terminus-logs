# The Rust Markdown converter at `/app/` has bugs that cause it to produce incorre

- **UUID:** `f3fe938b-acb6-435b-b414-d0c80e4f333b`
- **Slug:** `the-rust-markdown-converter-at-app-has-bugs-that-cause-it-to`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

The Rust Markdown converter at `/app/` has bugs that cause it to produce incorrect HTML output and wrong statistics in `/app/output/report.json`. The tool reads `.md` files from `/app/input/`, converts each to an HTML file in `/app/output/`, and writes a JSON summary report.

The expected behavior for the parser and statistics generator is: - **Headings**: The parser must strictly assign heading levels based on the exact number of `#` characters (from 1 to 6). - **Code blocks**: Fenced code blocks must only be closed by a line that begins with a matching sequence of the exact same fence character (` ``` ` or `~~~`) that opened it.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
