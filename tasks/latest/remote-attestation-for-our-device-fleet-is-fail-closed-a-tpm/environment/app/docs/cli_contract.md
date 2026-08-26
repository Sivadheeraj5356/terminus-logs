# CLI contract

The attestor under `/app` exposes one offline program whose release artifact is
`/app/target/release/tpm2-quote-attestor`. Required flags (each exactly once):

| Flag | Path meaning |
|---|---|
| `--data-dir` | Cartridge directory (canonical layout under `/app/data`) |
| `--output` | Destination report path (canonical `/app/output/report.json`) |

Unknown flags, duplicate flags, missing required flags, and positional
arguments are fatal. Delete any stale `--output` first. Write bytes only to a
same-directory temporary sibling, then atomically rename onto `--output`. Do
not emit informational text on stdout. Build uses the vendored Cargo workspace
at `/app` with an offline locked release configuration.
