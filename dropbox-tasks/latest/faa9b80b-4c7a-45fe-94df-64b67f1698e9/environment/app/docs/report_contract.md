# Report contract

Normative JSON report produced by `lunar-regolith-solver` on success. The
machine-readable companion schema is `/app/docs/report_schema.json`. Both files
agree exactly on required structure and fields.

Scientific formulas appear in `data_contract.md`, `thermal_model_contract.md`,
`radiometer_contract.md`, and `inversion_contract.md`.

---

## Top-level keys

The report is one JSON object with **exactly** these top-level keys (no others):

| Key | Type | Description |
|-----|------|-------------|
| `time_step_rows` | array | One row per report-period time step per case |
| `temperature_rows` | array | Depth profiles at each observation time |
| `surface_flux_rows` | array | Surface / energy accounting per report step |
| `radiometer_rows` | array | Band radiance and brightness temperature |
| `inverse_fit_rows` | array | Bounded inversion results |
| `solver_diagnostics` | array | Per-case spin-up and range diagnostics |
| `summary` | object | Cross-case aggregates |

All numeric values must be finite (no NaN or infinity). Boolean and integer
fields retain their JSON types. Round floating-point values only immediately
before serialization using `output_decimal_places` from `solver_config.json`
(ties-to-even / banker's rounding is acceptable and matches common language
defaults).

Repeated successful runs on byte-identical inputs must produce byte-identical
JSON output after the documented sort passes.

---

## Atomic output

At startup, remove any stale file at the requested `--output` path.

On full success only:

1. Complete every forward case (spin-up + report period).
2. Complete every inversion fit.
3. Build the complete report in memory.
4. Validate it against this contract / `report_schema.json`.
5. Serialize deterministically.
6. Write to a temporary file in the output directory.
7. Flush and close the temporary file.
8. Atomically rename it to the requested output path.

On failure: exit nonzero, emit nonempty stderr, remove stale final output and
task-created temporary files, and emit no partial successful JSON. See
`failure_contract.md`.

---

## Row populations

| Array | Population rule |
|-------|-----------------|
| `time_step_rows` | One row per report-period step for every illumination case |
| `temperature_rows` | For every observation query whose `time_s` exists in that case's report history: one row per cell |
| `surface_flux_rows` | One row per report-period step for every illumination case |
| `radiometer_rows` | One row per observation query whose `time_s` exists in that case's report history |
| `inverse_fit_rows` | One row per fit in `inversion_queries.json` |
| `solver_diagnostics` | Exactly one row per illumination case |

Empty populations are legal only when the corresponding inputs are empty (for
example zero fits ⇒ empty `inverse_fit_rows`). Baseline fixtures are nonempty
for all sections.

---

## Semantic uniqueness keys

| Array | Unique key |
|-------|------------|
| `time_step_rows` | `(case_id, step_index)` |
| `temperature_rows` | `(case_id, observation_id, cell_index)` |
| `surface_flux_rows` | `(case_id, step_index)` |
| `radiometer_rows` | `observation_id` |
| `inverse_fit_rows` | `fit_id` |
| `solver_diagnostics` | `case_id` |

Duplicate keys are forbidden.

---

## Sort keys

After assembly, sort ascending by:

| Array | Sort key |
|-------|----------|
| `time_step_rows` | `(case_id, step_index)` |
| `temperature_rows` | `(case_id, observation_id, cell_index)` |
| `surface_flux_rows` | `(case_id, step_index)` |
| `radiometer_rows` | `(observation_id,)` |
| `inverse_fit_rows` | `(fit_id,)` |
| `solver_diagnostics` | `(case_id,)` |

Forward cases are processed in ascending `case_id` order. Fits are solved in
ascending `fit_id` order before the final sort (which is then a no-op if already
ordered).

---

## `time_step_rows`

### Fields (exactly these)

| Field | Type | Semantics |
|-------|------|-----------|
| `case_id` | string | Illumination case |
| `step_index` | integer | Zero-based index within the report period |
| `start_time_s` | number | Step start local time |
| `end_time_s` | number | Step end local time (`start_time_s + time_step_s`) |
| `nonlinear_iterations` | integer | Nonlinear iterations used for the step |
| `maximum_residual_w_m2` | number | Max absolute cell residual after the step |
| `converged` | boolean | `true` iff residual \(\le\) `nonlinear_residual_tolerance_w_m2` |

### Step-index rules

- `time_step_rows[].step_index` and `surface_flux_rows[].step_index` are
  zero-based.
- The first report-period step is `0`.
- Indices reset to `0` for each case.
- Spin-up steps are not emitted and do not consume indices.
- A case with \(N\) report steps uses the contiguous sequence \(0 \ldots N-1\).

---

## `temperature_rows`

### Fields (exactly these)

| Field | Type | Semantics |
|-------|------|-----------|
| `case_id` | string | Illumination case |
| `observation_id` | string | Exact identity copied from `observation_queries.csv` |
| `time_s` | number | Observation / step-end time |
| `cell_index` | integer | Cell index |
| `depth_center_m` | number | Cell center depth |
| `temperature_k` | number | Cell temperature at `time_s` |

---

## `surface_flux_rows`

### Fields (exactly these)

| Field | Type | Semantics |
|-------|------|-----------|
| `case_id` | string | Illumination case |
| `step_index` | integer | Zero-based report step |
| `end_time_s` | number | Step end time |
| `absorbed_solar_flux_w_m2` | number | \(q_{\mathrm{solar}}\) |
| `emitted_thermal_flux_w_m2` | number | \(\varepsilon\sigma T_0^4\) |
| `conductive_flux_down_w_m2` | number | Downward face flux between cells 0 and 1 |
| `geothermal_flux_up_w_m2` | number | Case geothermal flux (upward) |
| `stored_energy_change_j_m2` | number | \(\sum_i[E_i^{\mathrm{new}}-E_i^{\mathrm{old}}]\) |
| `net_boundary_energy_j_m2` | number | \(\Delta t\,(q_{\mathrm{surface,down}}-q_{\mathrm{bottom,down}})\) |
| `energy_residual_j_m2` | number | `stored_energy_change_j_m2 - net_boundary_energy_j_m2` |

---

## `radiometer_rows`

### Fields (exactly these)

| Field | Type | Semantics |
|-------|------|-----------|
| `observation_id` | string | Exact identity copied from `observation_queries.csv` |
| `case_id` | string | Case |
| `time_s` | number | Observation time |
| `band_id` | string | Radiometer band |
| `surface_temperature_k` | number | Kinetic surface temperature (cell 0) |
| `band_radiance_w_m2_sr` | number | Band-effective radiance \(L_{\mathrm{band}}\) |
| `brightness_temperature_k` | number | Inverted \(T_b\) (no emissivity division) |

---

## `inverse_fit_rows`

### Fields (exactly these)

| Field | Type | Semantics |
|-------|------|-----------|
| `fit_id` | string | Fit identifier |
| `case_id` | string | Forward case used |
| `parameter_names` | array of string | Ordered names |
| `parameter_values` | array of number | Recovered values, parallel to names |
| `objective` | number | Final weighted SSE \(J\) |
| `evaluation_count` | integer | Forward evaluations used |
| `converged` | boolean | Convergence flag per `inversion_contract.md` |
| `at_parameter_bound` | boolean | Any parameter at a bound within tolerance |

---

## `solver_diagnostics`

### Fields (exactly these)

| Field | Type | Semantics |
|-------|------|-----------|
| `case_id` | string | Illumination case |
| `spinup_cycles` | integer | Spin-up periods executed before the report period |
| `final_spinup_difference_k` | number | Cycle difference that ended spin-up |
| `report_step_count` | integer | Number of report-period steps (`len(time_step_rows)` for the case) |
| `maximum_step_residual_w_m2` | number | Max of `maximum_residual_w_m2` over report steps |
| `minimum_temperature_k` | number | Minimum cell temperature in the report-period history |
| `maximum_temperature_k` | number | Maximum cell temperature in the report-period history |
| `all_values_finite` | boolean | `true` iff every report-period cell temperature is finite |

---

## `summary`

### Fields (exactly these)

| Field | Type | Aggregation population |
|-------|------|------------------------|
| `case_count` | integer | Number of illumination cases |
| `observation_count` | integer | `len(observation_queries.csv)` — every validated query row counts exactly once |
| `radiometer_row_count` | integer | `len(radiometer_rows)` |
| `inverse_fit_count` | integer | `len(inverse_fit_rows)` |
| `converged_inverse_fit_count` | integer | Count of inverse rows with `converged == true` |
| `minimum_surface_temperature_k` | number | Min of `surface_temperature_k` over `radiometer_rows` |
| `maximum_surface_temperature_k` | number | Max of `surface_temperature_k` over `radiometer_rows` |
| `maximum_brightness_temperature_k` | number | Max of `brightness_temperature_k` over `radiometer_rows` |
| `minimum_inversion_objective` | number | Min of `objective` over `inverse_fit_rows` |
| `maximum_absolute_energy_residual_j_m2` | number | Max of `abs(energy_residual_j_m2)` over `surface_flux_rows` |

### Empty-population behavior

When the aggregation population is empty, the corresponding floating-point
summary field is `0.0`. Integer counts remain `0`.

| Field | Empty population ⇒ value |
|-------|--------------------------|
| `minimum_surface_temperature_k` | no radiometer rows ⇒ `0.0` |
| `maximum_surface_temperature_k` | no radiometer rows ⇒ `0.0` |
| `maximum_brightness_temperature_k` | no radiometer rows ⇒ `0.0` |
| `minimum_inversion_objective` | no inverse fits ⇒ `0.0` |
| `maximum_absolute_energy_residual_j_m2` | no surface flux rows ⇒ `0.0` |
