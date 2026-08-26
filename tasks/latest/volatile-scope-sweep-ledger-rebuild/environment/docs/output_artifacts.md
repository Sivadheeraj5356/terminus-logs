# Output artifacts

| Path | Workflow |
|------|----------|
| `/app/output/sweep_ledger.json` | rebuild, merge |
| `/app/output/probe_snapshot.json` | probe |
| `/app/state/scope_state.json` | rebuild, merge |

Ledger JSON includes `profile`, `workflow`, `included_records`, `dropped_records`, `windows`, and workflow-specific digest fields.
