# Commands

The export command reads `/app/ops` and writes a regenerated bundle:

```bash
/usr/local/bin/rotlogctl export --root /app/ops --out /app/output/current
```

The verify command performs the same regeneration and exits nonzero when any authority disagrees:

```bash
/usr/local/bin/rotlogctl verify --root /app/ops --out /app/output/current
```

Legacy v1 compatibility is checked independently:

```bash
/usr/local/bin/rotlogctl legacy-verify --root /app/ops
```

The output directory is disposable. Treat `/app/ops/runtime`, `/app/ops/logs`, `/app/ops/state`, `/app/ops/manifests`, and `/app/ops/legacy` as the durable operator surfaces.
