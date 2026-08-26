# Inversion contract

Normative bounded parameter recovery from synthetic brightness temperatures.
Companion inputs: `data_contract.md`. Companion forward model:
`thermal_model_contract.md` and `radiometer_contract.md`.

---

## Supported parameters

Only these parameter names are allowed, in these combinations:

| Fit arity | `parameter_names` |
|-----------|-------------------|
| One parameter | `["conductivity_scale"]` |
| Two parameters | `["conductivity_scale", "albedo_offset"]` |

Any other name or arity is fatal.

When a fit overrides only `conductivity_scale`, the case's baseline
`albedo_offset` from `illumination_cases.csv` remains in force. When a fit
overrides both, both overrides replace the case defaults for that evaluation.

---

## Forward evaluation of a candidate

For every candidate parameter vector:

1. Rerun **complete** periodic spin-up for the fit's `case_id` using the
   candidate overrides.
2. Rerun the additional report period.
3. Recompute every requested radiometer observation for the fit's
   `observation_ids`.
4. Do **not** interpolate precomputed parameter solutions, cache fitted maps, or
   reuse another fit's temperature history.

Each such complete forward solve counts as one inversion evaluation against
`inversion_max_evaluations`.

---

## Objective

Weighted sum of squared errors on brightness temperature:

\[
J(\mathbf{p})
=
\sum_j
w_j
\bigl(
  T_{b,\mathrm{pred},j}(\mathbf{p})
  -
  T_{b,\mathrm{target},j}
\bigr)^2
\]

where

- \(T_{b,\mathrm{pred},j}\) is the predicted `brightness_temperature_k` for
  `observation_ids[j]`;
- \(T_{b,\mathrm{target},j}\) is `target_brightness_temperatures_k[j]`;
- \(w_j\) is `observation_weights[j]` (nonnegative).

Respect all parameter bounds. Candidates outside
`[lower_bounds[i], upper_bounds[i]]` are not evaluated; search methods must
project or stay inside the box.

---

## Allowed optimizers

Any deterministic bounded method is acceptable, including:

- golden-section search for one parameter;
- deterministic coordinate refinement;
- bounded pattern / grid search;
- another deterministic bounded method that honors the public tolerances.

Exact optimizer trajectories, evaluation orders, and intermediate candidates are
**not** normative. Reported `evaluation_count` must be a positive integer not
exceeding `inversion_max_evaluations`.

For the supplied one-parameter fixtures, a bracket-preserving golden-section
search is sufficient. For two parameters, a deterministic coarse box grid
followed by repeated bounded coordinate refinement is sufficient. The coarse
grid must include both bounds and the initial point. A fit must retain the
best candidate seen across all stages rather than returning the final trial
point. Objective comparisons must use the complete recomputed forward model.

The recovery verifier allows a small multiple of
`inversion_parameter_tolerance` because different valid optimizers stop at
different points inside the final bracket. It does not require the coordinates
of the Python reference optimizer.

### Acceptance is trajectory-independent

A deterministic bounded method is valid when it:

- respects parameter bounds;
- stays within the evaluation budget;
- satisfies the public convergence / objective rule;
- recovers the synthetic parameter values within the documented
  `inversion_parameter_tolerance`-based fixture tolerance;
- does not need to match one reference optimizer's final floating-point
  coordinates or evaluation order.

### Convergence

A fit may set `converged = true` when either:

- \(J \le \texttt{inversion\_objective\_tolerance}\), or
- for one-parameter search, the active parameter bracket width is within the
  documented parameter tolerance derived from
  `inversion_parameter_tolerance`.

`at_parameter_bound` is `true` when any recovered parameter lies within
`inversion_parameter_tolerance` of its lower or upper bound.

Exceeding `inversion_max_evaluations` without an accepted result is fatal.

---

## Baseline recovery fixtures

Canonical recovery fixtures (`fit_cond`, `fit_two`) are:

- identifiable from the supplied multi-band / multi-time observations;
- interior to the search box unless a test explicitly stresses bounds;
- numerically stable;
- recoverable within the documented tolerances when the forward model and
  radiometry match this contract set.

---

## Report row

Each fit emits one `inverse_fit_rows` object with fields defined in
`report_contract.md`:

`fit_id`, `case_id`, `parameter_names`, `parameter_values`, `objective`,
`evaluation_count`, `converged`, `at_parameter_bound`.

`parameter_values` is parallel to `parameter_names` and uses the same order.
