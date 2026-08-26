# Operations

The tick loop, profile loader, audit writer, metrics helpers, and runner shell are provided. Implement every function marked `// Stub:` in the Go tree per `build_obligations.md` so bundled profiles pass verifier checks.

## Runner

```bash
bash /app/environment/tools/runner.sh <profile.json> /app/output/schedule_audit.json
```

The runner rebuilds `/app/bin/dschedsim` and `/app/bin/sched_probe` when either binary is missing or when Go sources are newer than either binary.

## Completion probe

```bash
/app/bin/sched_probe --config <profile.json>
```

Reports `jobs_submitted`, `jobs_completed`, and `completion_ratio` only. Full schedule parity and digest alignment require the main driver output, not these counts alone.

## Bundled profiles

| Profile | Graph fixture | Purpose |
|---------|---------------|---------|
| `/app/environment/profiles/default.json` | `diamond_mesh` | Default verifier entry |
| `/app/environment/profiles/diamond_mesh.json` | `diamond_mesh` | Diamond dependency stall |
| `/app/environment/profiles/gradual_mesh.json` | `gradual_mesh` | Staggered submit diamond |
| `/app/environment/profiles/linear_smoke.json` | `linear_smoke` | Linear chain control |
| `/app/environment/profiles/fan_in.json` | `fan_in` | Wide fan-in dispatch |
| `/app/environment/profiles/cascade_wave.json` | `cascade_wave` | Multi-wave cascade with chain checkpoints |

Fixture paths live under `/app/environment/fixtures/`.

Graph topology is in `/app/environment/docs/graph_layout.md`.

Audit field definitions, partition ledger rules, and profile thresholds are in `/app/environment/docs/schedule_audit_schema.md`. Stub implementation obligations are in `/app/environment/docs/build_obligations.md`.

## Adversarial suite

`/app/environment/profiles/adversarial_suite.json` lists held-out profile variants. Every member must be runnable via `runner.sh` and must match steady/checkpoint parity rules for its geometry.

## Run modes

Profiles may set `run_mode`, `boundary_tick`, and `boundary_ticks`:

| Mode | Behavior |
|------|----------|
| `steady` | Continuous tick loop (default) |
| `checkpoint_resume` | Prefix through `boundary_tick`, snapshot, restore, finish horizon |
| `checkpoint_chain` | Snapshot and restore at each ascending `boundary_ticks` entry, then finish horizon |

Recommended boundaries for bundled stall profiles: `default`/`diamond_mesh` 6, `gradual_mesh` 5, `fan_in` 4, `linear_smoke` 3, `cascade_wave` chain `[5, 11, 17]`.

The verifier may synthesize variant profiles under `/app/output/variants/` when overriding `run_mode`, `seed`, `boundary_tick`, or `boundary_ticks`.

## Go packages

Coordination stub packages (see `build_obligations.md`):

- `vein/` — output exclusivity table and readability checks
- `weft/` — dependency ready-set and admission delay
- `rift/` — visibility epoch after publish when `strict_deps` is enabled
- `spine/` — checkpoint-chain boundary normalization
- `placement/` — node slot pool (provided)
- `drift/` — ready job queue and per-tick dispatch width
- `slate/` — boundary capture before reload
- `thaw/` — cold reload after boundary
- `grove/` — lane seal digest for checkpoint runs
- `internal/pipeline/` — tick loop and audit assembly (provided)
- `internal/metrics/` — summary percentile and utilization helpers (provided)
- `internal/lanes/` — lane state writer for checkpoint runs (provided)

## Environment root

Sources live under `/app/environment`. Set `DSCHEDSIM_ENV_ROOT` to override the root for local tooling.

## Offline image constraints

`schedule_fingerprint` recomputation uses the `sha256sum` utility with the digest format in `/app/environment/docs/schedule_audit_schema.md` (LF-joined lines, no trailing newline).

The image is offline (`allow_internet = false`). Pinned packages in `environment/verifier-requirements.txt` are installed only at image build time. Do not run `pip`, `apt-get`, `curl`, or `uv` to fetch packages during agent work.

The image uses a custom Go base (`public.ecr.aws/docker/library/golang:1.24-bookworm`). The Dockerfile preinstalls pinned `tmux=3.3a-3` and `asciinema=2.2.0-1` and verifies them with `tmux -V` and `asciinema --version` so runtime package installs are not required.
