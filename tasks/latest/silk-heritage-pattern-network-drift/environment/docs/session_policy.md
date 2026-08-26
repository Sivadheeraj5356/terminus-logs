# Session policy

## Genealogy journal modes

Environment switches for interrupted tracing:

- `TRACE_HALT=1` — run a full compile, write session and report payload to `/app/output/.genealogy_journal.json`. The `--out` path must not be written; after a halt run the `--out` file is absent (false that the report path exists).
- `TRACE_RESUME=1` — when the journal exists **and** its `network_seal` matches a fresh compile context, publish the committed journal body; otherwise perform a full cold compile. A cold compile followed by `TRACE_RESUME=1` must agree with a single cold compile for the same bundle and registries when the journal is absent or stale.

Panel catalog rows and bundle declarations live under `/app/data/panels/catalog.json` and `/app/data/bundles/`.
