# TOF mass-axis reconcile contract

## Metrology scope

This is a scientific mass-metrology numerical workflow. Reconcile correlated cubic
TOF mass-axis candidates from local instrument telemetry and Markdown lab notebooks,
propagate full parameter covariance into corrected-mass uncertainty, assign catalog
ions with a global one-to-one matcher, reject mass outliers, and emit a version-2
axis report for board review.

Network access is limited to localhost. The instrument telemetry base URL is passed
on the CLI (`--api`). Verifier scenarios use at most 16 catalog ions.

## Active shot

Use only `run_id` from the CLI. Ignore other shots returned by `/v1/runs`.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness (`{"ok": true}`) |
| GET | `/v1/runs` | Shot roster |
| GET | `/v1/runs/{run_id}/calibration` | Vector axis candidates from the instrument |
| GET | `/v1/runs/{run_id}/peaks` | Measured peak arrival times |
| GET | `/v1/catalog/ions` | Catalog calibrant ions in daltons |

### Calibration payload

```json
{
  "run_id": "shot-2025-0314",
  "active": {
    "candidate_id": "api-active",
    "k": 0.0, "t0": 0.0, "q": 0.0,
    "sigma_k": 0.0, "sigma_t0": 0.0, "sigma_q": 0.0,
    "rho_k_t0": 0.0, "rho_k_q": 0.0, "rho_t0_q": 0.0,
    "k_units": "Da_per_us2", "t0_units": "us", "q_units": "Da_per_us3"
  },
  "archive": { "...": "same shape as active" }
}
```

Rules:

- Payload `run_id` must equal the CLI `--run-id`.
- When `active` is present and valid, discard `archive` completely.
- Do not substitute another run or an archive candidate.
- An invalid active instrument candidate is a hard input error.

### Peaks payload

```json
{
  "run_id": "shot-2025-0314",
  "peaks": [
    {"peak_id": "ion-118", "tof_us": 20.0, "tof_sigma_ns": 0.08, "intensity": 1200.0}
  ]
}
```

Payload `run_id` must equal the CLI `--run-id`. Convert `tof_sigma_ns` to microseconds
with `tof_sigma_us = tof_sigma_ns / 1000.0`.

### Catalog payload

```json
{
  "ions": [
    {"ion_id": "ESI-L-118", "mz_da": 118.086255, "sigma_da": 0.00015}
  ]
}
```

Catalog masses are already daltons. Duplicate `ion_id` values or missing required
fields are hard input errors. Verifier scenarios use at most 16 ions.

## Candidate vector and covariance

Each axis candidate is the coupled vector

```text
theta = [k, t0, q]^T
```

with a full symmetric `3 x 3` covariance `C` in canonical units:

- `k`: `Da/us^2`
- `t0`: `us`
- `q`: `Da/us^3`

Construct

```text
C_ii = sigma_i^2
C_ij = rho_ij * sigma_i * sigma_j
```

Reject non-finite values, non-positive sigmas, correlations outside `[-1, 1]`, and
matrices that are not strictly positive definite. Use a deterministic Cholesky (or
equivalent) SPD test; positive diagonals alone are not sufficient.

### Unit conversion

Convert both the vector and covariance with a diagonal scale matrix `S`:

```text
theta_canonical = S * theta_source
C_canonical = S * C_source * S^T
```

Supported unit tokens (case-insensitive):

| coefficient | tokens | scale into canonical |
|-------------|--------|----------------------|
| `k` | `Da_per_us2`, `Da/us^2` | `1` |
| `k` | `mDa_per_us2`, `mDa/us^2` | `1/1000` |
| `t0` | `us` | `1` |
| `t0` | `ns` | `1/1000` |
| `q` | `Da_per_us3`, `Da/us^3` | `1` |

Unsupported unit tokens for a coefficient make that candidate invalid.

## Lab notes

Scan every `*.md` file under `--notes` recursively.

### Which tables count

Only Markdown tables whose preceding heading (`##` or `###`) contains the exact
token `axis_candidate` contribute candidates. Tables under any other heading are
decoys and must not contribute.

### Required columns

Case-insensitive; any column order:

```text
candidate_id, rev, status,
k, t0, q,
sigma_k, sigma_t0, sigma_q,
rho_k_t0, rho_k_q, rho_t0_q,
k_units, t0_units, q_units
```

### Parsing rules

- Strip HTML comments (`<!-- ... -->`, including newlines) before parsing.
- Only `active` rows are eligible.
- Each Markdown file is one source.
- Within a file, keep the greatest `rev` for each `candidate_id`.
- For equal revision, choose the row with the smaller generalized uncertainty
  `g(C) = det(C)^(1/6)` after canonical conversion.
- If still tied, choose the lexicographically smaller normalized row serialization
  so traversal order cannot decide the winner.
- Directory order, file order, table order, and row order must not affect results.

Normalized row serialization for ties (UTF-8):

```text
candidate_id=<id>|rev=<rev>|k=<k:.12e>|t0=<t0:.12e>|q=<q:.12e>|c00=<c00:.12e>|c01=<c01:.12e>|c02=<c02:.12e>|c11=<c11:.12e>|c12=<c12:.12e>|c22=<c22:.12e>
```

using canonical coefficients and covariance entries after conversion.

### Candidate keys

- Instrument active: `instrument::<candidate_id>`
- Notebook row: `<relative-path-from-notes>::<candidate_id>@<rev>`

Use `/` separators in relative paths. These keys are used for tie-breaking and
provenance.

## Physical admissibility

A candidate is admissible only if the cubic axis is strictly increasing over the
measured TOF interval `[min_tof, max_tof]` of the requested run's peaks.

```text
dt = tof - t0
m(tof) = k * dt^2 + q * dt^3
m'(tof) = 2*k*dt + 3*q*dt^2
```

Evaluate `m'` at both endpoints and, when `q != 0`, at the stationary point
`dt = -k/(3*q)` if that TOF lies inside the interval. Require

```text
min m'(tof) > monotonicity_eps
```

with `monotonicity_eps = 1e-9`.

Notebook candidates that fail are excluded with reason `non_monotonic`.
An invalid or non-monotonic instrument active candidate is a hard input error.

Invalid notebook covariance (after conversion) is excluded with reason
`invalid_covariance`. Superseded same-`candidate_id` rows use reason `superseded`.

## Platform lock and robust generalized least squares

Use `g(C) = det(C)^(1/6)`.

- If there are no admissible notebook candidates, use the active instrument vector
  and covariance with source `api_only`.
- If `g(C_api) <= 0.4 * min(g(C_lab))` over admissible notebook candidates, use the
  active instrument vector and covariance exactly with source `api_lock`.
- Otherwise perform robust GLS on the instrument active candidate plus all
  admissible notebook candidates:

```text
P = sum(inv(C_i))
C_hat = inv(P)
theta_hat = C_hat * sum(inv(C_i) * theta_i)
```

For each notebook candidate evaluate

```text
d_i^2 = (theta_i - theta_hat)^T * inv(C_i + C_hat) * (theta_i - theta_hat)
```

If the largest notebook `d_i^2` exceeds `11.344866730144373`, remove exactly that
notebook candidate as `gls_outlier` and recompute. Never remove the instrument
active candidate. Repeat until all remaining notebook candidates satisfy the
threshold or none remain.

For equal `d_i^2` within `1e-12`, remove the lexicographically larger canonical
candidate key.

Final source:

- `robust_gls` when at least one notebook candidate remains in the GLS result
- `api_only_after_rejection` when robust rejection removed every notebook candidate

Implement real `3x3` matrix operations. Do not reduce this to three independent
inverse-variance averages and do not drop off-diagonal covariance.

## Mass model and uncertainty propagation

```text
dt = tof_us - t0
corrected_da = k * dt^2 + q * dt^3
```

Parameter Jacobian and full propagation:

```text
J_theta = [ dt^2,  -2*k*dt - 3*q*dt^2,  dt^3 ]
dm_dtof = 2*k*dt + 3*q*dt^2
sigma_corr^2 = J_theta * C_hat * J_theta^T
               + (dm_dtof * sigma_tof_us)^2
```

Preserve covariance cross terms.

## Global one-to-one peak assignment

Constants:

- `match_window_da = 0.015`
- `k_sigma = 2.5`

An edge between peak `p` and catalog ion `j` exists only when

```text
abs(corrected_da_p - mz_da_j) <= match_window_da
```

Cost:

```text
cost(p, j) = residual_da^2 / (sigma_corr_da^2 + sigma_catalog_da^2)
```

Choose an assignment by priority:

1. Maximum number of matched peaks
2. Minimum total cost
3. Lexicographically smallest sorted sequence of `peak_id=catalog_id` pairs

A catalog ion may be assigned to at most one peak. Unassigned peaks are `no_match`.

For an assigned peak:

```text
residual_da = corrected_da - catalog_da
z_score = residual_da / sqrt(sigma_corr_da^2 + sigma_catalog_da^2)
```

If `abs(z_score) > 2.5`, mark `accepted=false`, `reject_reason="outlier"`; otherwise
`accepted=true`, `reject_reason=null`. For `no_match`, `catalog_id`, `catalog_da`,
`residual_da`, and `z_score` are JSON `null`.

## Report artifact

Write pretty-printed JSON (2-space indent, trailing newline) to `--out`.

### Schema binding

The `--schema` argument is required:

- Parse the supplied file as JSON.
- Require the exact marker `"x-tofmass-report-version": 2`.
- Compute lowercase SHA-256 over the exact schema file bytes and store it as
  `schema_digest`.
- Invalid JSON, wrong marker, or missing schema file must fail before replacing
  `--out`.

A full JSON Schema validator is not required.

### Required top-level fields

```text
schema_version, producer, run_id, api_base, schema_digest,
axis, provenance, peaks, summary, ledger_digest
```

`schema_version` must be `2`. `producer` must be `tofmass`.

### `axis`

```text
k, t0, q,
covariance_order,   // exactly ["k","t0","q"]
covariance,         // 3x3 nested arrays, row-major symmetric
source,             // api_only | api_lock | robust_gls | api_only_after_rejection
monotonic_interval_us  // [min_tof, max_tof]
```

### `provenance`

```text
used_candidate_keys      // lexicographically sorted
rejected_candidates      // {candidate_key, reason} sorted by (candidate_key, reason)
```

Rejection reasons: `superseded`, `invalid_covariance`, `non_monotonic`, `gls_outlier`.

### Peak objects

```text
peak_id, tof_us, tof_sigma_us, corrected_da, sigma_corr_da,
catalog_id, catalog_da, residual_da, z_score, accepted, reject_reason
```

Sort `peaks` by `peak_id` ascending.

### Summary

Counts: `matched`, `accepted`, `rejected`, `no_match`, `outlier`.

```text
weighted_rms_z = sqrt(sum(z_score^2) / matched)   over assigned peaks
max_abs_z = max(|z_score|)                         over assigned peaks
```

Both residual metrics are JSON `null` when `matched == 0`.

### Numeric tolerances (verifier)

- `k`: `1e-9`
- `t0`: `1e-9`
- `q`: `1e-14`
- masses / residuals / z: `1e-9`
- sigmas / covariance: relative `1e-9` or absolute `1e-18`, whichever is larger

## Canonical ledger

UTF-8 SHA-256 hex digest (lowercase) over the canonical ledger string.

Line grammar:

```text
schema|version=2|sha256=<schema_digest>
axis|k=<k:.12e>|t0=<t0:.12e>|q=<q:.12e>|c00=<c00:.12e>|c01=<c01:.12e>|c02=<c02:.12e>|c11=<c11:.12e>|c12=<c12:.12e>|c22=<c22:.12e>|source=<axis_source>
used|<candidate_key>
rejected|<candidate_key>|<reason>
peak|<peak_id>|tof=<tof_us:.10f>|sigma_tof=<tof_sigma_us:.12e>|mass=<corrected_da:.10f>|sigma=<sigma_corr_da:.12e>|catalog=<catalog_id-or->|residual=<residual:.10f-or-null>|z=<z_score:.10f-or-null>|accepted=<0-or-1>|reason=<reject_reason-or->
```

Emit one `used` line per used candidate key in lexicographic order, then one
`rejected` line per rejected entry sorted by `(candidate_key, reason)`, then one
`peak` line per peak sorted by `peak_id`. Join with a single `\n` and **no**
trailing newline before hashing.

The report and digest must be invariant to API JSON object ordering, catalog
ordering, peak ordering, note directory traversal order, note file order, and
candidate table row order. The digest must change when a real numerical input,
covariance term, source decision, assignment, or rejection reason changes.

## Atomic failure behavior

Complete all validation and computation before replacing `--out`.

Write through a temporary file in the destination directory, flush, `fsync`, then
`rename` over the target. On any error:

- return non-zero
- leave any pre-existing output byte-for-byte unchanged
- remove temporary files
- do not emit a partial valid-looking report
