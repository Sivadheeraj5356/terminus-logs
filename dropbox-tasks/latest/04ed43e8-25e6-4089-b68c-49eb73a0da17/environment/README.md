# state-audit workspace

Offline replay harness for volatile-workspace coordination traces after parallel bring-up.

## Build

Set `GOCACHE` and `GOMODCACHE` to writable directories when rebuilding outside the image (for example `/tmp/gocache` and `/tmp/gomodcache`).

```bash
go build -o /app/bin/state-audit ./driver/
```

## Run

```bash
/app/bin/state-audit \
  --trace /app/output/coordination_trace.json \
  --workspace /app/data/workspace \
  --fixtures /app/environment/fixtures/cycle
```

## Scripts

- `/app/environment/scripts/setup_workspace.sh` — bootstrap workspace views and published slot
- `scripts/exec_replay.sh` — shell wrapper around state-audit for operators
- `scripts/write_load.sh` — append synthetic load lines during manual probes

Contract formulas live in `docs/coordination_contract.md`. Digest prefixes are recomputed with `sha256sum` over the documented byte strings.

## Workspace layout

Volatile coordination state lives under `/app/data/workspace`:

- `/app/data/workspace/journal/staging.log` — append-only staging tail
- `/app/data/workspace/journal/cursor` — durable cursor after flush
- `/app/data/workspace/gate/latch` — generation latch bytes used for lineage binding

Published slot and layered views are created by `setup_workspace.sh` (see `docs/coordination_contract.md`).

## Verifier pipeline

Pytest rebuilds from `/app/environment`, bootstraps the workspace, and reruns state-audit:

```bash
go build -o /app/bin/state-audit ./driver/
bash /app/environment/scripts/setup_workspace.sh /app/data/workspace /app/environment/fixtures/cycle
/app/bin/state-audit --trace /app/output/coordination_trace.json --workspace /app/data/workspace --fixtures /app/environment/fixtures/cycle
```

Harbor passes `--ctrf` to pytest for its own logging; you do not need to wire that flag into your state-audit workflow.
