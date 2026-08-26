# Failure contract

Normative fatal-error behavior for `lunar-regolith-solver`. Diagnostic message
prose is not compared; only exit status, stderr nonemptiness, and output-file
cleanup are required.

---

## Required invocation

```text
lunar-regolith-solver --data-dir PATH --output PATH
```

Defaults when flags are omitted:

- `--data-dir /app/data`
- `--output /app/output/report.json`

Every execution must reread all runtime inputs from `--data-dir`.

---

## On any fatal condition

The process must:

1. Exit with a **nonzero** status code.
2. Print a **nonempty** diagnostic to **stderr**.
3. Remove any stale file at the requested `--output` path.
4. Remove any task-created temporary output files in the output directory
   (for example `*.tmp` companions used for atomic writes).
5. Emit **no** partial successful JSON report at `--output`.

Stdout may be empty. Exact stderr wording is unrestricted.

---

## Fatal input conditions

Treat as fatal:

- Missing required input file under `--data-dir`.
- Unreadable or empty required CSV/JSON.
- Missing required CSV columns or JSON keys.
- Non-finite numeric input values.
- Duplicate IDs where uniqueness is required (`material_id`, `case_id`,
  `observation_id`, `fit_id`, etc.).
- Unresolved foreign keys (`material_id`, `case_id`, `band_id`,
  `eclipse_profile_id`, observation IDs referenced by fits).
- Depth-grid violations (non-contiguous cells, gaps/overlaps, nonzero top of
  cell zero, nonpositive thickness, non-contiguous indices).
- Forcing-interval violations (incomplete period coverage, overlaps, boundaries
  not aligned to `time_step_s`).
- Eclipse-profile violations (transmission outside \([0,1]\), non-increasing
  times after sort).
- Radiometer-band violations (fewer than two samples, non-increasing
  wavelengths, negative response, nonpositive response integral).
- Observation times not on report-period step boundaries.
- Unsupported inversion parameter names or arities.
- Bound / length inconsistencies in `inversion_queries.json`.
- `solver_config.json` missing required keys or containing invalid limits
  (nonpositive time step, inverted temperature bounds, nonpositive iteration
  budgets, negative decimal places, etc.).

---

## Fatal thermal conditions

Treat as fatal:

- Non-finite temperatures or residuals during time stepping.
- Temperatures outside
  `[minimum_temperature_k, maximum_temperature_k]`.
- Nonlinear step failing to meet `nonlinear_residual_tolerance_w_m2` within
  `nonlinear_max_iterations`.
- Periodic spin-up failing to meet `spinup_tolerance_k` within
  `maximum_spinup_cycles`.
- Non-finite energy-accounting quantities on an accepted report step.

---

## Fatal radiometry conditions

Treat as fatal:

- Nonpositive band response integral.
- Failure to produce a finite brightness temperature within
  `brightness_temperature_max_iterations` when a valid bracket exists and
  radiance is positive.
- Non-finite band radiance or brightness temperature.

---

## Fatal inversion conditions

Treat as fatal:

- Unsupported parameter set.
- Missing observation IDs or target/weight length mismatches.
- Exceeding `inversion_max_evaluations` without an accepted result.
- Non-finite objective or parameter values.

---

## Fatal output conditions

Treat as fatal:

- Report that violates `report_contract.md` / `report_schema.json`.
- Any NaN or infinity in the assembled report.
- Failure to create the output directory, temporary file, flush, or atomic
  rename.

---

## Non-requirements

- Exact diagnostic prose is not required.
- Exact nonlinear iteration counts are not required for success beyond the
  public residual tolerance.
- Exact optimizer trajectories are not required beyond public inversion
  tolerances and bounds.
