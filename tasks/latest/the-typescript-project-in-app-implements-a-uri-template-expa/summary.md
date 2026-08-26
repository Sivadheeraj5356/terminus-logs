# The TypeScript project in `/app` implements a URI Template expander that has to

- **UUID:** `d3ffba0a-6c5d-48ad-8195-543d5490bdb2`
- **Slug:** `the-typescript-project-in-app-implements-a-uri-template-expa`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

The TypeScript project in `/app` implements a URI Template expander that has to satisfy the Level 4 template-expansion rules of RFC 6570. It consumes a single JSON object on standard input, shaped as `{"template": <string>, "variables": <object>}`, in which `variables` binds each name to a string, a list, or an associative object; it emits the fully expanded string on standard output, closed by one newline.

A template that is not syntactically valid under RFC 6570 must not be expanded at all — the program prints the token `ERROR` and exits with a non-zero status. Compiling with `make` (a `tsc` build) yields the launcher `/app/uritmpl`, and that executable is what the standard uritemplate-test conformance vectors are run against.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
