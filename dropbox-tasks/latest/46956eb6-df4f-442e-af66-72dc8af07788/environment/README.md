# Telemetry replayer

C sources live under `/app/src`. Build with `make -C /app` or `bash /app/scripts/build.sh`.

The replayer walks three LMDB DBI partitions, resolves per-scenario correlation windows from `/app/config/replayer.toml`, and emits per-scenario diagnostics consumed by the matrix driver.

The shipped matrix driver at `/app/scripts/run_matrix.py` must invoke `/app/bin/telreplay` for each pack row, read `/app/output/.single_report.json`, and append each parsed object before assembling the matrix envelope. Replacing that driver with a Python reimplementation that synthesizes reports without invoking the binary is insufficient.

`/app/bin/telreplay` must be a native ELF executable linked against `liblmdb`.

CLI usage: `telreplay --db PATH --scenario ID --loops N` (see sources under `/app/src`).

Runtime base image: digest-pinned `debian:bookworm-slim` from the platform canonical ECR mirror (C toolchain plus Python verifier dependencies installed in the Dockerfile).

Runtime references:

- `/app/docs/keyspace_layout.md` — LMDB key byte layouts
- `/app/docs/correlation_policy.md` — window lookup rules and triple definition
- `/app/data/scenarios.json` — pack schema with `id`, `db_path`, and `loops` per scenario row
