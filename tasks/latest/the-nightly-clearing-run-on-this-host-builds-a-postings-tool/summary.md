# The nightly clearing run on this host builds a postings tool entirely from vendo

- **UUID:** `ef1c3782-c4d7-4b86-9f76-74ba4e1c57a0`
- **Slug:** `the-nightly-clearing-run-on-this-host-builds-a-postings-tool`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

The nightly clearing run on this host builds a postings tool entirely from vendored sources and then uses it to turn a binary tape of settlement records into a postings report. Since a recent change to the tool the build still completes and the tool still runs, but downstream reconciliation keeps rejecting the report: the amounts come out right for the small shipped tape and wrong for larger ones.

Everything the build needs is under /app/vendor and /app/build, and no network is available. The vendored kit at /app/vendor/reckit holds the record-format library recfmt.fs and the FORMAT descriptor, which together set out how one record frame is laid out and how each field is meant to be read from the tape.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
