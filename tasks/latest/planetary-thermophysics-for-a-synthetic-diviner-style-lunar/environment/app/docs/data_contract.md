# Data contract

Normative input layout for the lunar-regolith thermal inertia and eclipse
inversion solver. All runtime inputs are read from the directory given by
`--data-dir` (default `/app/data`). File row order is never trusted; semantic
sort keys below define the authoritative order after load.

Every CSV must contain a header row matching the required column names exactly.
Every numeric field must be finite. Cross-file identifiers must resolve.

---

## `materials.csv`

### Required columns

| Column | Type | Unit / meaning |
|--------|------|----------------|
| `material_id` | string | Unique material identifier |
| `density_kg_m3` | number | Bulk density \(\rho\) |
| `heat_capacity_c0_j_kg_k` | number | Heat-capacity coefficient \(c_0\) |
| `heat_capacity_c1_j_kg_k2` | number | Heat-capacity coefficient \(c_1\) |
| `heat_capacity_c2_j_kg_k3` | number | Heat-capacity coefficient \(c_2\) |
| `contact_conductivity_w_m_k` | number | Contact conductivity base |
| `conductivity_depth_gradient_per_m` | number | Linear depth gradient of contact conductivity |
| `radiative_conductivity_w_m_k4` | number | Radiative conductivity coefficient |
| `surface_albedo` | number | Broadband surface albedo in \([0,1]\) |
| `surface_emissivity` | number | Broadband surface emissivity in \([0,1]\) |

### Heat capacity

\[
c_p(T) = c_0 + c_1 T + c_2 T^2
\]

with \(T\) in kelvin.

### Cell energy per unit horizontal area

For cell \(i\) with thickness \(\Delta z_i =\) `bottom_depth_m` \(-\) `top_depth_m`:

\[
E_i(T) = \rho_i \,\Delta z_i \left[
  c_0 T + \tfrac{1}{2} c_1 T^2 + \tfrac{1}{3} c_2 T^3
\right]
\]

Units: \(\mathrm{J\,m^{-2}}\).

### Conductivity

\[
k_i(T,z) =
\texttt{conductivity\_scale}
\cdot \texttt{contact\_conductivity}
\cdot \bigl(1 + \texttt{conductivity\_depth\_gradient\_per\_m}\cdot z\bigr)
+ \texttt{radiative\_conductivity}\cdot T^3
\]

where \(z\) is the cell center depth in meters and `conductivity_scale` comes from
the illumination case or an inversion override.

### Validation

- `material_id` values must be unique.
- Density must be strictly positive.
- Heat capacity \(c_p(T)\) must be strictly positive for every temperature in
  `[minimum_temperature_k, maximum_temperature_k]` from `solver_config.json`.
- Conductivity \(k_i(T,z)\) must be strictly positive for every cell center depth
  and every temperature in that same configured range when
  `conductivity_scale > 0`.
- `surface_albedo` must lie in \([0,1]\).
- `surface_emissivity` must lie in \([0,1]\).
  - `surface_emissivity = 0.0` is valid for synthetic insulated / no-emission
    fixtures.
  - Zero disables the thermal \(\varepsilon\sigma T^4\) surface loss and
    produces zero graybody band radiance.
  - Positive values use the same declared emissivity in both thermal and
    radiometric equations.
  - Values below 0 or above 1 are fatal. Do not clamp invalid values.

Baseline fixture material: `lunar_regolith`.

---

## `depth_grid.csv`

### Required columns

| Column | Type | Unit / meaning |
|--------|------|----------------|
| `case_id` | string | Illumination case identifier |
| `cell_index` | integer | Zero-based cell index within the case |
| `top_depth_m` | number | Depth of the cell top face (downward positive) |
| `bottom_depth_m` | number | Depth of the cell bottom face |
| `material_id` | string | Reference into `materials.csv` |
| `initial_temperature_k` | number | Initial cell temperature |

### Rules

- Cell indices begin at zero and form a contiguous sequence \(0 \ldots N-1\).
- Cells are contiguous: `bottom_depth_m` of cell \(i\) equals `top_depth_m` of
  cell \(i+1\).
- No gaps or overlaps between adjacent cells.
- `top_depth_m` of cell zero is exactly `0`.
- `bottom_depth_m` is strictly greater than `top_depth_m` for every cell.
- Semantic sort key: `(case_id, cell_index)` ascending.
- File row order is not trusted.

### Derived geometry

\[
\texttt{depth\_center\_m} = \frac{\texttt{top\_depth\_m} + \texttt{bottom\_depth\_m}}{2}
\]

\[
\Delta z = \texttt{bottom\_depth\_m} - \texttt{top\_depth\_m}
\]

Baseline fixtures use six nonuniform cells per case for `case_diurnal`,
`case_eclipse`, and `case_gradient`.

---

## `illumination_cases.csv`

### Required columns

| Column | Type | Unit / meaning |
|--------|------|----------------|
| `case_id` | string | Unique case identifier |
| `period_s` | number | Forcing period length |
| `solar_flux_w_m2` | number | Incident solar flux scale |
| `geothermal_flux_w_m2` | number | Upward geothermal heat flux at the base |
| `conductivity_scale` | number | Forward-model conductivity scale |
| `albedo_offset` | number | Additive albedo offset |
| `spinup_tolerance_k` | number | Maximum absolute cell \(\Delta T\) for spin-up convergence |
| `maximum_spinup_cycles` | integer | Maximum spin-up periods before failure |

### Effective albedo

\[
\texttt{effective\_albedo} = \mathrm{clamp}(\texttt{surface\_albedo} + \texttt{albedo\_offset},\, 0,\, 1)
\]

Canonical baseline cases must not require clamping. Inversion overrides may
produce values that clamp.

Baseline cases: `case_diurnal`, `case_eclipse`, `case_gradient`.

---

## `forcing_intervals.csv`

### Required columns

| Column | Type | Unit / meaning |
|--------|------|----------------|
| `case_id` | string | Illumination case |
| `interval_seq` | integer | Sequence within the case (any unique ordering key) |
| `start_time_s` | number | Interval start within \([0, \texttt{period\_s}]\) |
| `end_time_s` | number | Interval end |
| `cos_incidence_start` | number | Cosine of incidence at `start_time_s` |
| `cos_incidence_end` | number | Cosine of incidence at `end_time_s` |
| `eclipse_profile_id` | string | Reference into `eclipse_profiles.csv` |

### Rules

- For each case, intervals cover exactly one period: the first starts at `0` and
  the last ends at `period_s`.
- Intervals are contiguous and do not overlap (except shared endpoints).
- Cosine of incidence is linearly interpolated within each interval.
- Negative interpolated incidence is clipped to zero before absorption.
- Interval boundaries must align with the configured `time_step_s` grid.
- Semantic sort key: `(case_id, interval_seq)` ascending.

### Absorbed solar flux

\[
q_{\mathrm{solar}}(t) =
(1 - \texttt{effective\_albedo})
\cdot \texttt{solar\_flux\_w\_m2}
\cdot \max\bigl(0,\, \cos i(t)\bigr)
\cdot \tau_{\mathrm{eclipse}}(t)
\]

where \(\tau_{\mathrm{eclipse}}(t)\) is the eclipse transmission for the interval's
`eclipse_profile_id` at local time \(t\).

---

## `eclipse_profiles.csv`

### Required columns

| Column | Type | Unit / meaning |
|--------|------|----------------|
| `eclipse_profile_id` | string | Profile identifier |
| `profile_time_s` | number | Time within the forcing period |
| `transmission_fraction` | number | Transmission \(\tau\) in \([0,1]\) |

### Rules

- `transmission_fraction` must lie in \([0,1]\).
- After semantic sorting by `(eclipse_profile_id, profile_time_s)`, times within
  each profile are strictly increasing.
- Interpolation is linear between tabulated points.
- Exact table times use the exact tabulated transmission.
- Endpoint behavior outside the tabulated range: clamp to the first or last
  tabulated transmission value (no extrapolation).
- Profile `none` has transmission identically one at all times (may be
  implemented as a constant-one table or an explicit special case returning `1`).

Baseline profiles: `none`, `partial_eclipse`.

---

## `radiometer_bands.csv`

### Required columns

| Column | Type | Unit / meaning |
|--------|------|----------------|
| `band_id` | string | Band identifier |
| `sample_index` | integer | Sample order key within the band |
| `wavelength_um` | number | Wavelength in micrometers |
| `response` | number | Relative spectral response (nonnegative) |

### Rules

- At least two samples per band.
- After sorting by `sample_index`, wavelengths must be strictly increasing.
- Response values must be finite and nonnegative.
- The trapezoidal response integral over wavelength (converted to meters) must be
  strictly positive.
- Semantic sort key: `(band_id, sample_index)` ascending.
- File order is not trusted.

Baseline bands: `band_8um`, `band_25um`.

---

## `observation_queries.csv`

### Required columns

| Column | Type | Unit / meaning |
|--------|------|----------------|
| `observation_id` | string | Unique observation identifier |
| `case_id` | string | Forward case to observe |
| `time_s` | number | Observation time within the report period |
| `band_id` | string | Radiometer band |

### Rules

- `observation_id` is the exact semantic identity supplied by this file. It must
  be unique and is copied byte-for-byte into `temperature_rows` and
  `radiometer_rows`. Implementations must not synthesize, renumber, normalize,
  or replace it.
- `case_id` must exist in `illumination_cases.csv`.
- `band_id` must exist in `radiometer_bands.csv`.
- Observation times must lie on report-period step boundaries:
  \(t = n \cdot \texttt{time\_step\_s}\) for integer \(n\) with
  \(0 < t \le \texttt{period\_s}\). Observations are evaluated at the end of the
  time step that finishes at `time_s`.
- Each validated observation query emits one radiometer row and the applicable
  temperature rows.

---

## `inversion_queries.json`

Top-level object:

```json
{ "fits": [ /* fit objects */ ] }
```

### Each fit object

| Field | Type | Meaning |
|-------|------|---------|
| `fit_id` | string | Unique fit identifier |
| `case_id` | string | Forward case used for predictions |
| `parameter_names` | array of string | Ordered parameter names |
| `lower_bounds` | array of number | Inclusive lower bounds (same length) |
| `upper_bounds` | array of number | Inclusive upper bounds (same length) |
| `initial_values` | array of number | Starting values within bounds |
| `observation_ids` | array of string | Observations used in the objective |
| `target_brightness_temperatures_k` | array of number | Targets matching `observation_ids` |
| `observation_weights` | array of number | Nonnegative weights matching `observation_ids` |

### Supported parameter sets

Exactly one of:

1. `["conductivity_scale"]`
2. `["conductivity_scale", "albedo_offset"]`

Any other parameter name or arity is fatal.

Array lengths for bounds, initials, observation IDs, targets, and weights must
agree with `parameter_names` / `observation_ids` as appropriate.
`lower_bounds[i] <= initial_values[i] <= upper_bounds[i]` and
`lower_bounds[i] < upper_bounds[i]`.

Baseline fits: `fit_cond` (one-parameter), `fit_two` (two-parameter).

---

## `solver_config.json`

Required keys (all present, all finite where numeric):

| Key | Type | Meaning |
|-----|------|---------|
| `stefan_boltzmann_w_m2_k4` | number | Stefan–Boltzmann constant \(\sigma\) |
| `planck_constant_j_s` | number | Planck constant \(h\) |
| `boltzmann_constant_j_k` | number | Boltzmann constant \(k_B\) |
| `speed_of_light_m_s` | number | Speed of light \(c\) |
| `time_step_s` | number | Backward-Euler step size |
| `nonlinear_temperature_tolerance_k` | number | Finite-difference / convergence temperature scale |
| `nonlinear_residual_tolerance_w_m2` | number | Max absolute residual for a converged step |
| `nonlinear_max_iterations` | integer | Max nonlinear iterations per step |
| `line_search_min_factor` | number | Minimum line-search step factor when used |
| `minimum_temperature_k` | number | Hard lower temperature bound |
| `maximum_temperature_k` | number | Hard upper temperature bound |
| `energy_balance_tolerance_j_m2` | number | Allowed energy residual magnitude for acceptance checks |
| `brightness_temperature_tolerance_k` | number | Brightness-temperature root residual tolerance |
| `brightness_temperature_max_iterations` | integer | Max brightness root iterations |
| `inversion_parameter_tolerance` | number | Parameter convergence / bound proximity tolerance |
| `inversion_objective_tolerance` | number | Objective convergence tolerance |
| `inversion_max_evaluations` | integer | Max forward evaluations per fit |
| `output_decimal_places` | integer | Digits for pre-serialization rounding |

No hidden physical constants or tolerances are permitted. All solver limits used
by the implementation must come from this file or from the CSV/JSON inputs above.

---

## Load semantics

1. Read every file listed in this contract from `--data-dir` on every execution.
2. Sort each table by its semantic key before use.
3. Reject missing files, missing columns, non-finite numerics, unresolved foreign
   keys, and any validation failure above as fatal (see `failure_contract.md`).
