# zonepub

Offline DNSSEC publication tool for registry operators.

## Commands

```bash
make -C /app build

/app/bin/zonepub publish --workspace /work/normal --output-dir /output --epoch 1735689600
/app/bin/zonepub import-snapshot --workspace /work/rollback --snapshot /work/rollback/operator-snapshot-v1.json
/app/bin/zonepub inspect-manifest --manifest /output/publication-manifest.json --format json
```

## Publication model

The publisher reconciles trusted inventory, previous signed output, append-only
history, and optional operator snapshots into a single publication plan. It
stages unsigned input, invokes `dnssec-signzone`, validates staged artifacts,
and promotes the signed zone plus manifest.

Manifest schema version 2 is documented under `testdata/schema/`. Snapshot
version 1 remains importable for backwards compatibility.

Schema version 2 manifests expose `serial` and a `keys` array. Each entry
records `key_tag`, `role`, and `status` for the DNSKEY lineage reflected in
the release.

## Workflows

Reset writable copies from `/data` with `/app/scripts/reset-workflows.sh`.
Reproduce visible cases with `/app/scripts/repro.sh {normal,interrupted,rollback,wrap}`.
