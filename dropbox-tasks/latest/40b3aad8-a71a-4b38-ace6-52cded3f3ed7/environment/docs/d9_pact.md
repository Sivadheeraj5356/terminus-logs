# Output pact (d9_pact)

## Bundled walk instances

Graded instance uids in `/app/environment/fixtures/set_a/`.

| uid   | mesh_id | class_code | seed labels |
|-------|---------|------------|-------------|
| uid_a | 110     | 11         | 101, 102    |
| uid_b | 120     | 12         | 201         |
| uid_c | 100     | 10         | 100         |

Each row `instance_uid` field reports one graded id from this table (basis rows may append `#bN`). Instance `uid_a` means mesh 110 with seed labels 101 and 102. The `class_code` field must match the basis sizing table in `o8_flow.md`. The index may list additional series rows under other annex slices; graded output must include only slice 759 instances from this table.

## Driver command

```bash
npm run build --prefix /app/environment && node /app/environment/dist/d9_run.js --dump-dir /app/environment/fixtures/set_a --idx-store /app/environment/data/idx_store.db --out /app/output/inv_d9.yaml
```

Rebuild before validating.

Terminal artifact at `/app/output/inv_d9.yaml`.

YAML schema at `/app/environment/schemas/artifact_d9.schema.json`.

Top-level fields

- `slice_id` (integer, must be 759)
- `profile` (integer, 0 strict)
- `rows` (array)

Each row object

| field          | type   | notes                               |
|----------------|--------|-------------------------------------|
| instance_uid   | string |                                     |
| mesh_id        | int    |                                     |
| class_code     | int    |                                     |
| labels         | array  | sorted ascending in output          |
| weights        | array  | three floats, four decimal places when serialized   |
| o8_score       | int    | non-negative for obligation eight   |
| lattice_label  | string |                                     |
| row_digest     | string | 64-char lowercase hex               |

## row_digest

Canonical string

```
{instance_uid}|{sorted_labels_csv}|{weights_csv}
```

`weights_csv` uses four decimal places per weight. Hash with sha256; emit lowercase hex (no `0x`).

## Basis sizing

Row count must equal sum of basis sizes from `o8_flow.md` for present class codes. No extra rows.

For bundled walk class codes 10, 11, and 12, expect exactly 7 rows.

## Recovery command

Before re-validation after a failed run, reset durable segment state with

```bash
mkdir -p /app/environment/k2d/seg_v
rm -f /app/environment/k2d/seg_v/cursor.dat
echo -n > /app/environment/k2d/seg_v/.reset
```

Idempotent. Repeated recovery plus a second driver run must yield identical `row_digest` values.

## Stage interim

`/app/output/stage/partial.yaml` may omit `o8_score`, `lattice_label`, and `row_digest`. Only terminal `inv_d9.yaml` is graded.

## Overapprox inclusion

For each held-out ordering in `hold_d9.toml`, witness label sets in rows must be supersets of instance seed label sets after fold.

## Enclosure stress

```bash
python3 /app/environment/tools/q9_cycle.py --seed 759 --cycles 40
```

Must exit zero when the workspace is correct.
