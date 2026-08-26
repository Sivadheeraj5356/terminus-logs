# Machine-learning training workflow — recovery & deterministic replay

Offline **machine-learning** training orchestration used by the ML platform to
execute supervised model-training DAGs (feature ingest → train/eval → publish)
with training-checkpoint recovery, deterministic experiment replay, and a signed
ML recovery certificate for model lineage audit.

## Pipeline (A → H)

| Stage | Package | Artifact |
|-------|---------|----------|
| A Parser | `internal/parser` | `state/normalized.json` |
| B Compiler | `internal/compiler`, `internal/dag`, `internal/graph` | `state/compiled.json` |
| C Scheduler / Executor | `internal/scheduler`, `internal/executor` | `state/schedule.json`, `state/execution.json` |
| D Checkpoint | `internal/checkpoint`, `internal/journal` | `state/checkpoints.json` |
| E Recovery | `internal/recovery` | `state/recovery.json` |
| F Replay | `internal/replay` | `state/replay.json` |
| G Verification | `internal/verification` | `state/verification.json` |
| H Certificate | `internal/certificate` | `output/certificate.json` |

Contracts are specified under `docs/` (start with `docs/ml-overview.md`).

## Build & Run

```bash
export RUNTIME_ROOT=$PWD
export RUNTIME_BIN=/tmp/runtime
make build
bash scripts/run_pipeline.sh
bash scripts/verify.sh
```

Environment variables override `configs/policy.json` (see `docs/pipeline.md`).

## Requirements

- Go 1.24+
- Bash
- No network access at runtime
- Deterministic mocked training execution (no sleeps, no RNG)
