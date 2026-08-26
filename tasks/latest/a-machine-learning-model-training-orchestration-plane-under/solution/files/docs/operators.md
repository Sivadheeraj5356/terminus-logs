# Operator Runbook

## Clean run

```bash
export RUNTIME_ROOT=/app
export RUNTIME_BIN=/tmp/runtime
make clean build
bash scripts/run_pipeline.sh
bash scripts/verify.sh
```

## Inspect artifacts

- `state/normalized.json` — parser output
- `state/compiled.json` — DAG order + plan digest
- `state/execution.json` — node results
- `state/journal.json` — append-only execution journal
- `state/checkpoints/*` — versioned snapshots
- `output/certificate.json` — recovery certificate

## Common failure modes

1. Plan order missing nodes → compiler/graph issue
2. Replay timestamps contain fractional seconds → replay clock issue
3. Certificate signature mismatch → hash domain or HMAC issue
4. Epoch is 1999-01-01 or retries stay at file values → policy load order (env must be last; do not re-apply the file after env)
5. Workers assigned in reverse lex order → scheduler sorting issue
6. Independent digest recomputation mismatches → DomainHash missing `"\n"` separator or wrong payload shape
7. Workflow `id` mismatches Truncate16(DomainHash("workflow-id", name+"\n"+version)) → parser identity payload

## Recovery drill

```bash
RUNTIME_FAIL_NODE=train bash -c '$RUNTIME_BIN fail-run'
bash scripts/recover.sh
bash scripts/replay.sh
bash scripts/verify.sh
```
