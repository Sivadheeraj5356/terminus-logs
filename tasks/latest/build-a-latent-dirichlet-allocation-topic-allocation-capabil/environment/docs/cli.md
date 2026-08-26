# CLI surface

`ldactl` exposes four subcommands and takes no positional arguments.

- `ldactl ingest` reads every `*.json` file from the selected inbox and atomically materializes `/app/state/lda-corpus-staging.json` (see `document-format.md` and `vocabulary.md`).
- `ldactl sample` reads only `/app/state/lda-corpus-staging.json`, runs the collapsed-Gibbs sampler, and atomically materializes `/app/state/lda-count-staging.json` (see `initialization.md`, `conditional.md`, `count-ledger.md`, and `burn-in.md`).
- `ldactl export` reads only the two state snapshots and atomically materializes `/app/output/lda-topic-rollup.json` (see `topic-ranking.md` and `rollup-export.md`).
- `ldactl status` prints a one-line summary derived only from the state snapshots. It must never read the output file.

Each command exits nonzero when a required input is absent or invalid, and a failing command must not leave its target artifact behind. Every artifact is written as compact JSON (no spaces after separators) with a single trailing newline. Re-running a command whose inputs are unchanged must not alter the target file's bytes or modification time.

The inbox is `inbox` in `/app/config/ldactl.toml`. When the environment variable `TB3_LDA_ROOT` holds an absolute path it replaces the configured inbox for `ingest`; a relative value is ignored. The staging, count, and output paths and all sampler hyperparameters are read from the same configuration file.
