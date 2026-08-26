# Piezoelectric resonance audit contract (schema v4)

`piezo-audit` ingests one or more segmented `.chip` resonator calibration files spanning one or more families, resolves dated and inherited calibration profiles, merges chip inputs per family, and writes a batch JSON audit report. Successful runs maintain a branched manifest and optional row cache under `/app/output/`.

## Chip file format (`.chip`)

UTF-8 text. `#` starts an end-of-line comment.

Required header keys:

| Key | Rule |
|-----|------|
| `family_id=` | Non-empty family token |
| `chip_id=` | Non-empty canonical resonator identifier |
| `profile_id=` | Non-empty calibration profile identifier (must exist in the profile catalog) |
| `nominal_hz=` | Positive nominal frequency in hertz |

Optional header keys:

| Key | Rule |
|-----|------|
| `alias=` | Alternate label recorded in provenance; defaults to empty string when omitted |

A `readings:` line opens the measurement block. Readings are organized into **segments**:

- `segment: <segment_id>` starts a segment (`segment_id` is a non-empty token without spaces).
- Optional segment directives immediately after `segment:` (before reading rows):
  - `alpha_override=` — when present and positive, replaces the profile `alpha` for readings in this segment only.
  - `nominal_hz_override=` — when present and positive, replaces the chip `nominal_hz` for ppm pull in this segment only (profile-level nominal override still applies first when both exist).
- Reading rows belong to the current segment until the next `segment:` line.
- Before the first `segment:` line, the implicit segment id is `default`.

Reading row format:

```
<line_index> <temp_c> <freq_hz>
```

- `line_index` — positive integer label from the source file (1-based convention).
- `temp_c` — temperature in degrees Celsius.
- `freq_hz` — measured frequency in hertz.

At least one reading row is required per file.

## Calibration profile catalog

Profiles live as `.prof` files under `/app/environment/fixtures/profiles/`. Each file contains:

| Key | Rule |
|-----|------|
| `profile_id=` | Profile identifier |
| `effective_date=` | `YYYY-MM-DD` revision date |
| `inherits=` | Optional parent `profile_id`; when omitted, the revision is standalone |
| `alpha=` | Temperature coefficient (ppm/°C scale factor). When absent or non-positive after parsing, inherit from the resolved parent chain |
| `nominal_hz_override=` | Optional; when positive, replaces chip `nominal_hz` for ppm pull |
| `deprecation_window_days=` | Non-negative integer days (default `0`). Governs how long a superseded revision remains eligible after a newer same-`profile_id` revision becomes effective |

A catalog may contain multiple revisions sharing the same `profile_id` with different `effective_date` values.

### Profile inheritance

When `inherits=` is present, unresolved `alpha` and `nominal_hz_override` values are taken from the parent's revision selected for the same `as_of` date using the same eligibility rules. Inheritance chains must not cycle. The resolved parent revision's `effective_date` is recorded in provenance as `profile_parent_effective_date` (empty string when no inheritance).

### Profile selection and deprecation

The CLI accepts `--as-of YYYY-MM-DD` (default `2099-12-31` when omitted).

For each chip file, consider every catalog revision with matching `profile_id` and `effective_date <= as_of`.

A revision **R** is **superseded** when another revision **R'** exists with the same `profile_id`, `R'.effective_date > R.effective_date`, and `R'.effective_date <= as_of`.

**R** is **deprecated** at `as_of` when it is superseded by **R'** and `as_of > R'.effective_date + R'.deprecation_window_days`.

Among revisions that are not deprecated, select the one with maximal `effective_date`.

Record the chosen `effective_date` as `profile_effective_date` in provenance.

### Profile graph hash

```
profile_graph_hash = sha256(
  for each distinct resolved revision used in the run (including inherited parents), sorted by (profile_id, effective_date):
    profile_id + "|" + effective_date + "|" + alpha + "|" + nominal_hz_override + "|" + inherits + "|" + deprecation_window_days + "\n"
  for each segment override applied in the run, sorted by (family_id, chip_id, segment_id):
    family_id + "|" + chip_id + "|" + segment_id + "|" + alpha_override + "|" + nominal_hz_override + "\n"
)
```

Prefix with `sha256:` in the report. Render numeric fields as decimal numerals without exponent notation (trailing fractional zeros omitted). Use `0` for absent or non-positive overrides; use empty string for absent `inherits`.

The report field `profile_graph_hash` is the run's **profile version** fingerprint. Manifest rollback keys and row-cache invalidation use `(input_fingerprint, profile_graph_hash)`; the JSON field name remains `profile_graph_hash`.

## Temperature correction

For each reading, use the **effective alpha** for that reading's segment (segment override when positive, otherwise selected profile alpha):

```
freq_25_hz = freq_hz / (1 + alpha * (temp_c - 25))
```

Round `freq_25_hz` to four decimal places (half away from zero).

## Pull from nominal

Use the **effective nominal** for the reading's segment: segment `nominal_hz_override` when positive, else profile `nominal_hz_override` when positive, else chip `nominal_hz`.

```
ppm_pull = (freq_25_hz - nominal_hz) / nominal_hz * 1_000_000
```

Round `ppm_pull` to four decimal places (half away from zero).

## Weighted mean pull

- weight = `1` when `temp_c` is exactly `25`
- weight = `1 / |temp_c - 25|` otherwise

```
weighted_mean_ppm = sum(ppm_pull * weight) / sum(weight)
```

Round to four decimal places (half away from zero). Values exactly halfway between two four-decimal candidates round away from zero (e.g. `0.00005` → `0.0001`, `-1.23495` → `-1.2350`).

## Reading order

**Sort key:** `(temp_c, line_index)` ascending — compare `temp_c` first, then break ties with `line_index` (the file's 1-based row label).

- `readings` in the batch report use this order.
- `rows` inside each family's `resonance_digest` use the **same** `(temp_c, line_index)` order as that family's `readings` (not file order and not `segment_id` order).

## Multi-family batch processing

`--chip` paths are processed left to right. Chips may belong to different `family_id` values in one run.

Group chips by `family_id`. Process each family independently for merge, calibration, and provenance, then emit one batch report.

Within a family:

- Merge key is `(chip_id, profile_id)`.
- When the same merge key appears in multiple files, the **last** file replaces earlier readings for that key.
- The family entry's `chip_id`, `profile_id`, `alias`, and `nominal_hz` come from the **last** `--chip` file in that family.
- Active `readings` are those from the last file's merge key after applying replacement rules.

Families in the batch report are sorted by `family_id` ascending.

## Alias collision resolution

Across **all** `--chip` files in CLI order (all families):

- Track non-empty `alias` strings.
- When a new file's `alias` equals an earlier file's `alias` but `chip_id` differs, rewrite the **earlier** provenance entry's `alias` to `original_alias + "@" + earlier_chip_id`.
- The later file keeps the bare `alias` in provenance.
- Family-level report `alias` fields are unaffected by collision rewriting (they still reflect the last file in that family).

## Source provenance

Each family entry's `source_provenance` lists **every** `--chip` path for that family in CLI order. Each entry:

| Field | Rule |
|-------|------|
| `path` | CLI path string |
| `family_id` | parsed family |
| `chip_id` | canonical chip id |
| `alias` | alias after collision resolution |
| `profile_id` | parsed profile id |
| `profile_effective_date` | selected catalog date for this file |
| `profile_parent_effective_date` | parent's selected date, or `""` |
| `segment_ids` | segment ids in file order (unique, first-seen order) |
| `reading_count` | number of reading rows |
| `source_digest` | `sha256:` + lowercase hex of raw file bytes |

## Input fingerprint

```
input_fingerprint = sha256(
  as_of + "\n"
  + for each --chip path in order: utf8(path) + "\n" + raw_bytes + "\n"
)
```

Prefix with `sha256:`.

## Batch manifest (schema version 3)

Path: `/app/output/resonance_manifest.json`

```json
{
  "schema_version": 3,
  "batch_generation": <integer>,
  "last_input_fingerprint": "sha256:...",
  "last_profile_graph_hash": "sha256:...",
  "branches": [
    {
      "family_id": "<string>",
      "branch_generation": <integer>,
      "input_fingerprint": "sha256:...",
      "profile_graph_hash": "sha256:...",
      "parent_branch_generation": <integer or null>
    }
  ],
  "history": [
    {
      "batch_generation": <integer>,
      "input_fingerprint": "sha256:...",
      "profile_graph_hash": "sha256:..."
    }
  ]
}
```

**Batch key:** `(input_fingerprint, profile_graph_hash)`.

- When the batch key matches `last_input_fingerprint` + `last_profile_graph_hash`, `batch_generation` equals the stored `batch_generation` (minimum `1` on first success).
- When the batch key matches any `history` entry, reuse that entry's `batch_generation` (rollback-safe).
- Otherwise `batch_generation = max(history.batch_generation) + 1` (or `1` if history empty), append the new key to `history`, and update `last_*`.

**Branch key per family:** `(family_id, input_fingerprint, profile_graph_hash)`.

- When a branch key matches an existing `branches` entry, reuse its `branch_generation`.
- Otherwise assign `branch_generation = max(existing branch_generation) + 1` within the manifest (or `1` if no branches), set `parent_branch_generation` to the previous `batch_generation` when the batch key is new, else `null` on rollback.
- On success, upsert all family branches and update batch fields.
- On fatal input errors, remove only the requested `--out` file; an existing manifest must remain unchanged.

## Row cache

Path: `/app/output/resonance_row_cache.json`

```json
{
  "input_fingerprint": "sha256:...",
  "profile_graph_hash": "sha256:...",
  "families": {
    "<family_id>": [ ... ReadingRow with segment_id ... ]
  }
}
```

Reuse cached rows for a family only when **both** `input_fingerprint` and `profile_graph_hash` (profile version) match the current run. Corrupt cache JSON must be ignored.

## Output JSON (`schema_version` 4)

Top-level batch report:

| Field | Rule |
|-------|------|
| `schema_version` | integer `4` |
| `as_of_date` | `YYYY-MM-DD` from CLI |
| `input_fingerprint` | string |
| `profile_graph_hash` | string |
| `batch_generation` | per batch manifest rules |
| `family_count` | integer |
| `families` | array sorted by `family_id` ascending |
| `batch_digest` | `sha256:` + lowercase hex |

Each `families[]` object:

| Field | Rule |
|-------|------|
| `family_id` | string |
| `chip_id` | from last file in family |
| `alias` | from last file in family or `""` |
| `profile_id` | from last file in family |
| `nominal_hz` | float used for ppm on active chip (header nominal, not segment overrides) |
| `reading_count` | integer |
| `readings` | rows sorted by `(temp_c, line_index)` ascending |
| `readings[].line_index` | integer |
| `readings[].segment_id` | string |
| `readings[].temp_c` | float |
| `readings[].freq_hz` | float |
| `readings[].freq_25_hz` | float, four-decimal rounded |
| `readings[].ppm_pull` | float, four-decimal rounded |
| `weighted_mean_ppm` | float, four-decimal rounded |
| `branch_generation` | per branch manifest rules |
| `source_provenance` | array in CLI order for this family |
| `resonance_digest` | `sha256:` + lowercase hex |

## Canonical digest serialization

All digest hashes are `sha256:` + lowercase hex of UTF-8 bytes. Unless noted, JSON hash payloads use compact separators `,` `:` with no extra whitespace.

### Numeric rendering (hash payloads)

| Context | Rule |
|---------|------|
| Profile graph hash lines | Decimal numerals only; trim trailing fractional zeros; use `0` for absent/non-positive overrides |
| `profile_lineage` floats (`alpha`, `nominal_hz_override`) | Decimal only; trim trailing zeros; whole numbers render with `.0` suffix (e.g. `0.0`) |
| `rows` floats (`ppm_pull`, `temp_c`) | Decimal only; derive from four-decimal-rounded values; trim trailing zeros; whole numbers render with `.0` suffix (e.g. `25.0`, `0.0`) |
| Exponent notation | Never used in hash payloads |

### `profile_graph_hash` body (pipe lines, not JSON)

Concatenate one line per sorted revision, then one line per sorted segment override. Each line ends with `\n`.

Revision line:

```
profile_id|effective_date|alpha|nominal_hz_override|inherits|deprecation_window_days\n
```

Segment override line:

```
family_id|chip_id|segment_id|alpha_override|nominal_hz_override\n
```

**Golden example** (`golden_single.chip`, `as_of=2024-07-01`):

```
CAL-BASE|2024-01-01|0.000035|0||0
CAL-STD|2024-06-01|0.000035|0|CAL-BASE|90
FAM-GOLD-1|GOLD-1|hot|0.00005|0
```

→ `profile_graph_hash = sha256:360b08395dfe3c491991ae5eb287d2baa7616e10cf5fc41b9ba55ada9a108f2e`

### `resonance_digest` JSON payload (per family)

Build a JSON object with keys **in this order**:

1. `family_id` (string)
2. `chip_id` (string)
3. `profile_id` (string)
4. `profile_graph_hash` (string)
5. `as_of_date` (string)
6. `input_fingerprint` (string)
7. `branch_generation` (integer)
8. `reading_count` (integer)
9. `profile_lineage` (array) — sorted by `(profile_id, effective_date)`; each object keys in order: `profile_id`, `effective_date`, `inherits`, `alpha`, `nominal_hz_override`, `deprecation_window_days`
10. `provenance` (array) — CLI order for this family; each object keys in order: `path`, `family_id`, `chip_id`, `alias`, `profile_id`, `profile_effective_date`, `profile_parent_effective_date`, `segment_ids`, `reading_count`, `source_digest`
11. `rows` (array) — **same `(temp_c, line_index)` order as `readings`**; each object keys in order: `line_index`, `segment_id`, `ppm_pull`, `temp_c`

`segment_ids` encodes as a JSON array of strings via standard JSON string quoting.

**Golden single-family payload** (`golden_single.chip`, `branch_generation=1`):

```json
{"family_id":"FAM-GOLD-1","chip_id":"GOLD-1","profile_id":"CAL-STD","profile_graph_hash":"sha256:360b08395dfe3c491991ae5eb287d2baa7616e10cf5fc41b9ba55ada9a108f2e","as_of_date":"2024-07-01","input_fingerprint":"sha256:a1f8540ec08af5551549217b48ce643174eb25089c1a81270ec585710524b445","branch_generation":1,"reading_count":2,"profile_lineage":[{"profile_id":"CAL-BASE","effective_date":"2024-01-01","inherits":"","alpha":0.000035,"nominal_hz_override":0.0,"deprecation_window_days":0},{"profile_id":"CAL-STD","effective_date":"2024-06-01","inherits":"CAL-BASE","alpha":0.000035,"nominal_hz_override":0.0,"deprecation_window_days":90}],"provenance":[{"path":"/app/environment/fixtures/golden_single.chip","family_id":"FAM-GOLD-1","chip_id":"GOLD-1","alias":"","profile_id":"CAL-STD","profile_effective_date":"2024-06-01","profile_parent_effective_date":"2024-01-01","segment_ids":["hot","cold"],"reading_count":2,"source_digest":"sha256:7689b97c29ddabf10185d01f11954c5cfaf1da26d8d2d51d1e441cabcc3cea3f"}],"rows":[{"line_index":2,"segment_id":"cold","ppm_pull":0.0,"temp_c":25.0},{"line_index":1,"segment_id":"hot","ppm_pull":0.0,"temp_c":35.0}]}
```

→ `resonance_digest = sha256:a4ce09fe91db5fba7c509105af27a49cc330d7ec6afd0ec08bca1efcce1615d8`

Note `rows` order is `(temp_c, line_index)`: `(25.0, 2)` before `(35.0, 1)`.

### `batch_digest` JSON payload

The published batch report exposes `families[]`, but the **hash payload** uses internal names `family_count` and `family_digests`. Build a JSON object with keys **in this order**:

1. `schema_version` (integer `4`)
2. `as_of_date` (string)
3. `input_fingerprint` (string)
4. `profile_graph_hash` (string)
5. `batch_generation` (integer)
6. `family_count` (integer)
7. `family_digests` (array of `resonance_digest` strings in `family_id` ascending order)

**Golden multi-family payload** (`golden_multi_a.chip` + `golden_multi_b.chip`, fresh manifest):

```json
{"schema_version":4,"as_of_date":"2024-07-01","input_fingerprint":"sha256:dc9fd54ca23f9abfffe2f4d002839303162db74df524e5a4efa251a7c4180f21","profile_graph_hash":"sha256:0a6f3d11dadcee0178ce62087111c3749b28b1c088a66ab656b912a1b0956fdd","batch_generation":1,"family_count":2,"family_digests":["sha256:06caa6e93cad8b41dcd630ac8922b37ba4dd7ac538a94c1c0ab3639ca87f15db","sha256:84312e5d344b1bde2256b6eafdb831a24d5c07b2dc4ee86984fe7021db21f1bf"]}
```

→ `batch_digest = sha256:9cf4893eb6095effc039c52e42695c4998c9699bcf4766eda2cb72947f5a04b8`

Per-family `resonance_digest` values in `family_digests` carry each family's `branch_generation` inside their own payloads (`FAM-GOLD-A` → `1`, `FAM-GOLD-B` → `1`). `FAM-GOLD-B` includes segment override lineage in `profile_graph_hash` and segment `wing` with `alpha_override=0.00007` in provenance.

## Resonance digest (per family, v4)

Build a JSON object with keys **in this order**:

1. `family_id`
2. `chip_id`
3. `profile_id`
4. `profile_graph_hash`
5. `as_of_date`
6. `input_fingerprint`
7. `branch_generation`
8. `reading_count`
9. `profile_lineage` — sorted by `(profile_id, effective_date)`; each object keys: `profile_id`, `effective_date`, `inherits`, `alpha`, `nominal_hz_override`, `deprecation_window_days`
10. `provenance` — CLI order for this family; each object keys: `path`, `family_id`, `chip_id`, `alias`, `profile_id`, `profile_effective_date`, `profile_parent_effective_date`, `segment_ids`, `reading_count`, `source_digest`
11. `rows` — **same `(temp_c, line_index)` order as `readings`**; each object keys: `line_index`, `segment_id`, `ppm_pull`, `temp_c`

See **Canonical digest serialization** above for numeric rendering rules and golden examples.

## Batch digest

Build a JSON object with keys **in this order**:

1. `schema_version`
2. `as_of_date`
3. `input_fingerprint`
4. `profile_graph_hash`
5. `batch_generation`
6. `family_count`
7. `family_digests` — array in `family_id` order of each family's `resonance_digest` string

Hash UTF-8 with SHA-256; prefix `sha256:`. The hash payload field is `family_digests` even though the published report lists `families[]`.

## CLI

```
piezo-audit --chip <path>... --as-of <YYYY-MM-DD> --out <report.json>
```

- At least one `--chip` is required.
- On error, remove `--out` if it exists and exit non-zero. Do not modify the manifest.
- On success, write the report atomically: create a temporary file alongside `--out`, flush it, then rename into place. Pretty-printed JSON terminated by a newline.

## Default paths

Reference report: `/app/output/resonance_report.json`. Grading may use other valid paths.

## Grading harness

The verifier installs pytest with `apt-get install --no-install-recommends`, runs `UV_OFFLINE=1 pytest --ctrf /logs/verifier/ctrf.json`, rebuilds with `bash /app/environment/scripts/build.sh`, and invokes `/app/environment/bin/piezo-audit`. Harness module imports exercise the rebuilt CLI pipeline rather than a separate library API.

## Bundled fixtures

Chips: `/app/environment/fixtures/chip_a.chip`, `chip_b.chip`, `chip_a_early.chip`, `chip_a_late.chip`, `chip_family_b.chip`, `golden_single.chip`, `golden_multi_a.chip`, `golden_multi_b.chip`.

Profiles: `/app/environment/fixtures/profiles/`.
