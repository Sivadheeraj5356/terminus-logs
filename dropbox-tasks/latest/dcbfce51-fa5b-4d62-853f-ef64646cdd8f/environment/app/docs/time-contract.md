# Climate Model Time-Axis Contract

**Version:** 1.0  
**Authority:** This document is the authoritative numerical specification for calendar-qualified time coordinates, interval bounds, append ordering, climatological resampling bins, and trace report schema used by the `climconvert` climate time-axis engine.

**Important:** Preserving metadata strings (`calendar`, `units`) in output files is **necessary but not sufficient**. Semantic preservation requires that encoded numeric values continue to represent the same calendar instants and interval edges after every supported operation — the same requirement climate and earth-system models place on CF-compliant time axes.

---

## 0. Trace report version

The `trace` report JSON uses `schema_version` **3**.

## 1. Scope and environment

All time-axis logic operates in **UTC**. Human-readable timestamps in logs and trace output use ISO-8601 with `Z` suffix. The converter does not call host timezone databases or locale-dependent date parsers.

Supported calendars (exhaustive):

| Identifier | Description |
|------------|-------------|
| `gregorian` | Gregorian calendar with standard leap-year rules; dates before 1582-10-15 are not specially cased. |
| `proleptic_gregorian` | Gregorian rules extended backward indefinitely before 1582. |
| `noleap` | Fixed 365-day years; February always has 28 days. |
| `360_day` | Twelve 30-day months per year (360 days total). |

Unsupported calendars must be rejected by `validate` with non-zero exit.

Supported units (schema version 1):

```
days since YYYY-MM-DD HH:MM:SS
```

Only the `days` unit is supported. The origin datetime is parsed as UTC.

---

## 2. Canonical instant model

Internally and for verification, each time coordinate maps to a **canonical instant**:

```
CanonicalInstant = (calendar, year, month, day, hour, minute, second)
```

All comparisons, sort keys, append merge ordering, and resample bin assignment use canonical instants — **not** Unix epoch seconds, **not** days-since-1970, and **not** raw encoded floats without origin context.

### Encoding and decoding

A stored coordinate carries:

1. `calendar` — calendar identifier
2. `units` — full units string including origin
3. `encoded_value` — floating-point value in the declared units relative to the origin

Decoding procedure:

1. Parse origin `(Y0, M0, D0, h0, m0, s0)` from `units`.
2. Add `floor(encoded_value)` whole days to origin date using **the declared calendar's** month lengths and year lengths.
3. Fractional day remainder (if any) converts to hour/minute/second in UTC.

Encoding reverses this: given canonical instant and target units origin, compute the real number of days (including fraction) between origin and instant using the same calendar.

### Total order

Canonical instants are totally ordered by:

1. Compare `(year, month, day)` lexicographically in the shared calendar semantics.
2. Then compare `(hour, minute, second)`.

Cross-calendar comparison is undefined unless explicitly converted; append requires matching calendars.

---

## 3. Calendar arithmetic rules

### Gregorian and proleptic_gregorian

- Month lengths: Jan/Mar/May/Jul/Aug/Oct/Dec = 31; Apr/Jun/Sep/Nov = 30; Feb = 28 or 29.
- Leap year: divisible by 4, except centuries unless divisible by 400.
- `gregorian` and `proleptic_gregorian` differ only in documented interpretation of pre-1582 dates; arithmetic rules are identical in this tool.

### noleap

- Every year has 365 days; February has 28 days.
- No leap days under any circumstance.

### 360_day

- Every month has 30 days; year has 360 days.
- Month index wraps: day 31 of a 360_day month is invalid; arithmetic advances month after day 30.

### Worked decode example

Calendar: `360_day`  
Units: `days since 1850-01-01 00:00:00`  
Encoded: `90.0`

- 90 days from origin at 30 days/month → month 4 (April), day 1 → canonical `(1850, 4, 1, 0, 0, 0)`.

Changing only the units string to `days since 2000-01-01 00:00:00` with the same encoded `90.0` yields a **different** canonical instant. Tools must not compare or sort encoded values across different origins without normalization.

---

## 4. Interval bounds

Optional `bounds` arrays attach interval edges to each time cell. Each element is `[lower, upper]` in the same encoded units as the center coordinate.

### Semantic identity

Bounds represent **calendar-qualified intervals**, not opaque floats. After round-trip:

- Lower edge decodes to the same canonical instant as before.
- Upper edge decodes to the same canonical instant as before.

Bounds and center coordinates must use **the same normalization path**. Implementations that normalize centers and bounds through different code paths (e.g., centers via one epoch representation and bounds via another) violate this contract.

### Monotonicity

For each index `i`: `lower[i] < center[i] < upper[i]` in encoded units.  
Globally: `upper[i] <= lower[i+1]` is recommended but not strictly required for validation.

### Append with bounds

Both inputs must include bounds of matching structure, or neither may include bounds. Reordering during merge applies identically to centers and bound pairs.

---

## 5. Round-trip semantic preservation

For any supported single-file conversion path (`CCF→CFT→CCF` or reverse) without resample or append:

1. Each `time[i]` decodes to the same `CanonicalInstant` as the input.
2. Each `bounds[i]` (if present) decodes to the same edge instants.
3. Variable payload bytes are bit-identical.
4. `calendar` and `units` strings are preserved (echo allowed; must remain accurate).

**Regression constraint:** Gregorian monthly samples are the most common production case and must continue to round-trip correctly.

**Non-regression requirement:** The same rules apply to `proleptic_gregorian`, `noleap`, and `360_day`. A fix that special-cases only Gregorian while leaving other calendars coerced to Unix time is non-compliant.

---

## 6. Append ordering

See `APPEND.md` for CLI details. Contract summary:

- Merge key = canonical instant of each observation.
- Stable sort when canonical instants tie (preserve base before appendee).
- Output `units` defaults to base file units; encoded values are re-expressed in that units system.

### Mixed-origin compatible append

When base uses `days since 1850-01-01` and appendee uses `days since 2000-01-01` with the **same calendar**:

1. Decode each observation to canonical instant.
2. Sort all observations by canonical instant.
3. Re-encode into base units for output header.

Failure mode to avoid: sorting by raw encoded float or by Unix seconds — tail observations with small encoded values (relative to 2000 origin) incorrectly sort before head observations with large encoded values (relative to 1850 origin) even when the tail instants are chronologically later.

### Atomic rejection

Incompatible calendar or schema: exit non-zero, output path must not exist afterward.

---

## 7. Resample bin assignment

See `RESAMPLE.md` for CLI and cache details.

### Bin index

Given frequency `mon|sea|ann`, map canonical instant to bin index per calendar-aware climatological rules:

**Monthly (`mon`):** Bin by `(year, month)` in the dataset calendar. Each calendar month maps to one bin key `(year, month)`. Observations in the same calendar month aggregate together regardless of day offset within the month.

**Seasonal (`sea`):** Bin by season index `{DJF, MAM, JJA, SON}` derived from calendar month in the dataset calendar.

**Annual (`ann`):** Bin by calendar year.

After binning, output time coordinate lists one center per bin in ascending canonical order, encoded in input units.

### Aggregation

Follow per-variable `agg` field. Means use arithmetic mean; sums accumulate; min/max as expected.

### Cache identity

Cache keys must incorporate:

- `calendar`
- Full `units` string (including origin)
- Frequency
- Variable payload cryptographic digest
- Canonical time range (first and last instant)

Omitting calendar or units from cache keys causes stale wrong results when semantics change but numeric arrays appear similar.

---

## 8. Trace report schema (version 3)

Command:

```bash
climconvert trace --manifest /app/data/trace-manifest.toml --out /output/time-axis-trace.json
```

### Top-level JSON

```json
{
  "schema_version": 3,
  "generated_at": "1970-01-01T00:00:00Z",
  "scenarios": [ ... ]
}
```

- `schema_version` must be `3`.
- `generated_at` — UTC ISO-8601 timestamp (deterministic placeholder acceptable in offline builds).

### Scenario object

```json
{
  "name": "gregorian_roundtrip",
  "ok": true,
  "input_digest": "<sha256 hex of primary input bytes>",
  "instant_mismatch_count": 0,
  "bounds_hash": "<optional sha256 of bounds pairs>",
  "append_order_ok": null,
  "canonical_instant_sample": [0, 31, 59],
  "operation_hash": "<sha256 hex>",
  "notes": ""
}
```

| Field | Meaning |
|-------|---------|
| `ok` | `true` iff scenario passes all contract checks |
| `input_digest` | SHA-256 of first input file in scenario |
| `instant_mismatch_count` | Count of coordinates whose canonical instant differs from expected |
| `bounds_hash` | Digest of bounds array when applicable |
| `append_order_ok` | For append scenarios: merged axis strictly increasing in canonical order |
| `canonical_instant_sample` | Optional sample of encoded centers for smoke checks |
| `operation_hash` | Digest over scenario name and input paths/bytes |

### Manifest scenarios (bundled)

The trace manifest includes at minimum:

1. `gregorian_roundtrip` — CCF→CFT→CCF on Gregorian sample
2. `proleptic_roundtrip` — proleptic_gregorian sample
3. `360day_roundtrip` — 360_day calendar sample
4. `bounds_roundtrip` — bounds preservation
5. `mixed_units_append` — append with different compatible origins
6. `resample_monthly` — monthly resample after round-trip prep
7. `double_roundtrip_chain` — append → resample → CCF→CFT→CCF

Verifier-generated fixtures may use seed tag `0xC11MATE01` for hidden 360_day axis cases.

Trace evaluation must use the **same canonicalization** as convert, append, and resample. Special fast paths that skip canonical checks for individual scenarios mask bugs and are non-compliant.

---

## 9. Validation vs semantic correctness

`climconvert validate` performs structural checks:

- Format recognized
- Supported calendar string
- Strictly increasing encoded time array
- Consistent bounds length
- Variable byte layout

Passing validate does **not** imply correct calendar semantics. Agents must run trace and multi-calendar scenarios, not only Gregorian spot checks.

---

## 10. Design rationale

Climate and weather datasets (NetCDF-CF and derivatives) routinely separate:

1. Encoded numeric axis values
2. `units` attribute with reference epoch
3. `calendar` attribute
4. Optional `bounds` variable

Production tools often coerce (1) to Unix time internally while echoing (2) and (3) on output. Single-file Gregorian workflows appear correct; mixed-origin append and climatological resample expose silent drift.

`climconvert` models this failure class at manageable scope. Correct repair introduces a single authoritative calendar-qualified instant representation shared across parse, bounds, append, resample, cache, and trace.

---

## 11. Glossary

| Term | Definition |
|------|------------|
| Encoded value | Raw float in file `time` array |
| Origin | Reference datetime in `units` string |
| Canonical instant | Calendar-qualified absolute time |
| Echo | Metadata string preserved for output without semantic authority |
| Round-trip | Convert out and back without changing semantics |
| Compatible append | Same calendar, mergeable variable schema, units per APPEND.md |

---

## 12. References

- `FORMATS.md` — CCF/CFT byte layout
- `APPEND.md` — append compatibility and errors
- `RESAMPLE.md` — frequencies, aggregation, cache
- CF Conventions time coordinate conventions (informative; this contract is authoritative for `climconvert`)

---

*End of time-axis contract.*
