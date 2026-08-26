# Determinism Guarantees

The runtime guarantees byte-identical artifacts across clean runs when:

- `RUNTIME_EPOCH`, `RUNTIME_SEED`, `RUNTIME_WORKERS`, retries, and timeouts are fixed
- `state/`, `output/`, and `cache/` are emptied between runs
- `VERBOSE` is unset or `0` (so the pipeline driver does not rewrite `RUNTIME_ROOT`)

## Hash domains

| Domain | Purpose |
|--------|---------|
| `workflow-id` | Stable workflow identity |
| `workflow-canon` | Canonical workflow digest |
| `plan-v1` | Execution plan digest |
| `journal-v1` | Execution journal hash |
| `checkpoint-snap` | Checkpoint integrity |
| `recovery-v1` | Recovery result digest |
| `replay-v1` | Replay transcript hash |
| `verification-v1` | Verification report hash |
| `recovery-certificate-v1` | Certificate body digest |
| `cache-v1` | Execution cache keys |

All DomainHash values use `SHA256(domain + "\\n" + payload)`.
