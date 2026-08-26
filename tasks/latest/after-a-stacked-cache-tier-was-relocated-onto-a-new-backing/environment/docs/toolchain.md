# cvctl operator reference

Build the admin CLI:

```bash
cd /app/environment
export GOCACHE=/var/cache/cv-go
export GOMODCACHE=/var/cache/cv-gomod
export GOTOOLCHAIN=local
go build -o /tmp/cvctl /app/environment/cmd/cvctl
```

`go` is on `PATH` in the task image (`/usr/local/go/bin` and `/usr/local/bin/go`). Keep the Go build cache under `/var/cache/cv-go` rather than `/tmp`. Export `CVCTL_ROOT=/app/environment` when invoking `cvctl` outside `/app/environment`.

## cvctl flags

- `cvctl copy --sample <name> --dest /tmp/<scratch>`
- `cvctl status --workspace /tmp/<scratch>`
- `cvctl invariant --workspace /tmp/<scratch>`
- `cvctl recover --workspace /tmp/<scratch>`
- `cvctl read-replay --workspace /tmp/<scratch> --events <path>`

Sample fixtures live under `/app/environment/samples/`. Event logs live under `/app/environment/samples/run_*/events.jsonl`. Each sample directory contains a `workspace.json` seed that materializes lane JSON, reference rows, bind tables, origin alias, active ref, promotion seal, cache mode, and foreign payloads into the scratch tree.

## Workspace layout

Slow lane JSON: `/tmp/<scratch>/lanes/slow/<slot>.json`
Fast lane JSON: `/tmp/<scratch>/lanes/fast/<slot>.json`
Destination bind offsets: `/tmp/<scratch>/maps/dest_bind.json`
Origin alias: `/tmp/<scratch>/maps/origin_alias.json`
Active ref: `/tmp/<scratch>/refs/active.json`
Vault state: `/tmp/<scratch>/state/vault.json`
Foreign payloads: `/tmp/<scratch>/foreign/<id>.json`
Generated operator artifacts: `/tmp/<scratch>/out/`

`invariant` clears `/tmp/<scratch>/out/` before writing `probe_view.txt`. `recover` clears `out/` before regenerating operator artifacts. A following `read-replay` refreshes `tap_rows.jsonl` and `gauge.txt` without removing `clash_rows.jsonl` or `hash_view.json` when those were produced by recover.

## Package map

| Package | Role |
|---------|------|
| `internal/ops` | Command orchestration for recover, read-replay, invariant |
| `internal/plumb` | Sample copy and workspace materialization |
| `meridian` | Vault-side relocation lag signals |
| `horizon` | Frame assembly for cache mode and lagging state |
| `harbor` | Quorum witness for authority surface agreement |
| `anchor` | Recover-time rematerialization of pointer and alias |
| `ribbon` | Dirty gate, lane reconcile, settled tag selection |
| `splice` | Merge destination bind offsets into map rows |
| `pulse` | Tap generation and tally commit |
| `lens` | Post-settle payload selection for read-replay |
| `tablet` | Operator artifact rendering |
| `beacon` | Bind trace note formatting |
| `laneio` | Lane JSON read/write helpers |

Behavioral contracts for relocation windows, dirty gates, cache modes, tap tally rules, and artifact schemas are defined in `instruction.md`. Recompute `hash_view.fprint` with `docs/digest_ref.py` or the digest helper documented there.

## Artifact schemas

Generated files under `/tmp/<scratch>/out/`:

- `row_trace.jsonl`: each line has `seq`, `kind`, `slot`, `note`, `rev`. Bind rows use `kind` value `bind` and `note` values `off=<integer>` from the merged destination bind table.
- `hash_view.json`: `tag`, `rev`, `fprint`, `move`. `fprint` has length 16 per `docs/digest_ref.py`.
- `clash_rows.jsonl`: each line has `field`, `was`, `now`, `rev`.
- `tap_rows.jsonl`: each line has `seq`, `slot`, `payload`, `tally`, `gen`.
- `gauge.txt`: short operator gauge text that includes the substring `gauge ok`.
- `probe_view.txt`: single-line operator probe from `invariant` reporting whether the relocation window remains open or closed.
