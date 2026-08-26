# Stage command matrix

Run the four stages in order for each profile and timeline step. Rebuild after editing sources under `/app/environment`.

| Stage binary | Purpose |
|--------------|---------|
| `/app/bin/pull_gate` | Gate stage: `--profile <id> [--step N]` |
| `/app/bin/sync_probe` | Probe stage: `--profile <id> [--step N]` |
| `/app/bin/meta_walk` | Walk stage: `--profile <id> [--step N]` |
| `/app/bin/collect_stage` | Collect stage: `--profile <id> [--out /app/output/kv_export.json]` |

Fixture and seed semantics: `/app/environment/docs/seed_timelines.md`. Row layout: `/app/environment/docs/row_export.md`.

Rebuild command:

```bash
bash /app/ci/rebuild.sh
```

Verifier rebuild (from repository root inside the container): bash -c cd /app/environment && /app/ci/rebuild.sh

Profile timelines live under `/app/environment/fixtures/seed/<profile>/seed_steps.json`. The verifier may execute the same profile more than once in one session with different `--step` values.
