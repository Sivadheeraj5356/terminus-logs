# Climate Model Axis Serialization Formats

This document describes on-disk layouts for **CCF** (Climate Cube Format, binary) and **CFT** (Climate Flat Text, interchange) used by the `climconvert` time-axis engine. These are serialization views of the same calendar-qualified coordinate model defined in `time-contract.md`, not general-purpose data transforms.

## CCF (Climate Cube Format)

CCF is a binary container designed for efficient storage of multi-variable time-series cubes.

### File layout

| Offset | Size | Field |
|--------|------|-------|
| 0 | 4 | Magic bytes: `CCF1` |
| 4 | 4 | `json_len` — unsigned 32-bit little-endian length of JSON header |
| 8 | `json_len` | UTF-8 JSON header document |
| 8+json_len | remainder | Raw payload bytes (variable arrays) |

### JSON header schema (version 1)

```json
{
  "schema_version": 1,
  "calendar": "gregorian|proleptic_gregorian|noleap|360_day",
  "units": "days since 1850-01-01 00:00:00",
  "time": [0.0, 31.0, 59.0],
  "bounds": [[-15, 15], [16, 46]],
  "variables": {
    "temp": {"dtype": "f64", "offset": 0, "count": 3, "agg": "mean"},
    "precip": {"dtype": "f32", "offset": 24, "count": 3, "agg": "sum"}
  }
}
```

**Fields:**

- `schema_version` — must be `1`.
- `calendar` — one of the four supported calendar identifiers.
- `units` — CF-style units string; currently only `days since YYYY-MM-DD HH:MM:SS` is supported.
- `time` — array of encoded numeric time coordinates, one per observation, strictly increasing in encoded units.
- `bounds` — optional array of `[lower, upper]` pairs, same length as `time`. When present, each pair defines the interval edges for the corresponding cell.
- `variables` — map of variable name to definition:
  - `dtype` — `f64` or `f32`
  - `offset` — byte offset into payload
  - `count` — number of elements (must equal time axis length unless resampled)
  - `agg` — default aggregation for resample: `mean`, `sum`, `min`, `max`

### Payload

Variables are stored contiguously at their declared offsets. All multi-byte numeric values are little-endian. No compression is applied in schema version 1.

## CFT (Climate Flat Text)

CFT is a human-readable interchange format suitable for inspection and hand editing.

### Structure

1. **Metadata preamble** — lines beginning with `# key=value`
2. **Blank line** (optional)
3. **CSV section** — header row followed by data rows

### Required metadata keys

- `# calendar=<calendar_id>`
- `# units=<units_string>`
- `# schema_version=1`

Optional keys:

- `# bounds=<json_array>` — JSON-encoded bounds pairs
- Additional global attributes as `# name=value`

### CSV section

The first non-comment line is the header. It must include a `time` column plus one column per variable.

Example:

```
# calendar=gregorian
# units=days since 1850-01-01 00:00:00
# schema_version=1
time,temp,precip
0.0,10.5,0.1
31.0,11.0,0.2
```

### CCF ↔ CFT conversion rules

1. **Time coordinates** — numeric values round-trip exactly as IEEE doubles unless resampling alters the axis.
2. **Calendar and units strings** — preserved verbatim on round-trip (whitespace in units string is significant).
3. **Variable bytes** — payload bytes for each variable must be bit-identical after `CCF→CFT→CCF` for unmodified datasets.
4. **Bounds** — when present, encoded as JSON in CFT metadata and as array in CCF header.
5. **Global attributes** — CFT metadata keys (except `calendar`, `units`, `schema_version`, `bounds`) round-trip through the internal global attribute map.

### Whitespace normalization

CFT output always ends lines with a single newline. Trailing whitespace on metadata lines is stripped on read. CSV fields are not quoted; values must not contain commas.

## Validation

`climconvert validate` checks:

- Recognized format and magic/header syntax
- Supported calendar identifier
- Strictly increasing time array in encoded units
- Bounds length matches time length when present
- Variable byte counts match `count × element_size`

Validation does **not** prove calendar-correct instant identity — see `time-contract.md` for semantic requirements.
