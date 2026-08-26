# SDK ABI release contract

## Command

The release is produced by a single entry point:

```
bash /app/environment/runbook/release_pass.sh <matrix> <out-dir>
```

The public run uses the checked-in matrix and the canonical output directory:

```
bash /app/environment/runbook/release_pass.sh /app/environment/profiles/public.matrix /app/output/sdk-abi-index
```

The matrix is a whitespace-separated table of `lane profile_path` rows. Blank
lines and lines beginning with `#` are ignored. `profile_path` may be absolute,
relative to the environment root, or relative to the matrix file's directory.
Rows are processed top-to-bottom and that order is preserved in every artifact.

## Build tree

Each lane configures and builds under `/app/build/sdk-abi-index/<lane>/`. The
per-lane journal lives at `/app/build/sdk-abi-index/<lane>/.sdk-lane.journal`
(see `journal-contract.md`). The build tree is a cache: deleting it is never
required for a correct release, and a correct release never depends on it having
been wiped.

## Public artifacts (`<out-dir>`)

| file | shape |
| --- | --- |
| `manifest.json` | `{schema_version:1, matrix_path, matrix_sha256, record_count, records[]}` |
| `probe.jsonl` | one record object per matrix row, in row order |
| `provenance.json` | `{schema_version:1, environment_root, build_root, matrix_path, matrix_sha256, lanes[]}` |
| `loader_journal.tsv` | columns `lane  phase  field  status  detail` |
| `trace.tsv` | columns `phase  lane  path  detail` |

### Record schema (`manifest.records[]` and each `probe.jsonl` line)

```
{
  "lane": <string>,
  "profile_path": <absolute path>,
  "profile_sha256": <hex>,
  "configure_epoch": <int>,
  "generation_lineage": <int>,
  "generated": <layout view>,
  "compiled": <layout view>,
  "status": "match" | "mismatch"
}
```

A *layout view* is `{lane, record_size, align, field_count, digest?, fields[]}`
where each field is `{slot, name, ctype, offset, size}`. `status` is `match`
only when the generated and compiled views agree on `lane`, `record_size`,
`align`, `field_count`, and the full `fields` array. Slots are contiguous and
numbered from `0`.

### `provenance.lanes[]`

Each entry is `{lane, path, sha256, generated_digest, configure_epoch,
generation_lineage}`.

### `loader_journal.tsv`

One row per generated field per lane. `phase` is `legacy` for slots `0-11` and
`extension` otherwise. `status` is `accepted` when the generated slot, offset,
size, and ctype match the compiled probe, else `rejected`. Every lane must
accept all twelve legacy prefix fields.

### `trace.tsv`

Per lane the phases appear in this order: `configure`, then an optional
`reconcile` (only when a warm build tree is missing its generated header),
then `build`, `header`, `probe`.

## Legacy v1 prefix (slots 0-11)

The frozen prefix is identical in every lane and never moves:

| slot | field | ctype |
| --- | --- | --- |
| 0 | abi_version | uint32_t |
| 1 | name | const char* |
| 2 | checksum | uint64_t |
| 3 | dispatch | void* |
| 4 | reserved | uint32_t |
| 5 | capability_mask | uint64_t |
| 6 | lifecycle_epoch | uint64_t |
| 7 | allocator_cookie | void* |
| 8 | config_crc | uint32_t |
| 9 | telemetry_sink | void* |
| 10 | quarantine_tag | const char* |
| 11 | runtime_flags | uint32_t |

Lane-specific extension fields follow the prefix, contiguous, in physical
`pack.order` order for the fragments the lane selects.

## Preview header

`/app/environment/include/generated/sdk.hpp` is a non-authoritative preview
snapshot for editor tooling. The release always regenerates the real per-lane
header into the build tree before compiling the probe; the preview never steers
the released layout.
