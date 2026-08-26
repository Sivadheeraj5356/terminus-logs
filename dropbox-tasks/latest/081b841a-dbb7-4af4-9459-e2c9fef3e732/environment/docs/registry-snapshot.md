# Model registry snapshot

`/app/models/registry/` is the pinned snapshot of every model artifact the
ledger references. The layout mirrors the upstream registries:

```
registry/
  sentence-transformers/all-MiniLM-L6-v2/   # upstream snapshot
  orchid-internal/<model>/                  # internally published models
```

The ledger pins each model dependency to specific files in this snapshot via
its `artifacts` column (`path=digest` pairs, paths relative to `/app/models/`).

## Hashing procedure

`/app/bin/hash-artifacts` computes the integrity report the gate consumes:

```
openssl dgst -sha256 -r "<file>"
```

is run for every pinned path that exists on disk, and the results are written
to `/app/out/hash_report.json` as a `path -> lowercase hex digest` map. Files
that are pinned in the ledger but missing from the snapshot are omitted from
the report rather than reported as errors — deciding what a missing artifact
means is the policy's job, not the hasher's.

The snapshot is content-addressed and read-only in normal operation: publishing
a new model revision adds files and ledger pins; it never rewrites existing
files in place.
