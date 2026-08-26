# Thermal model contract

Normative one-dimensional finite-volume heat conduction model for lunar
regolith. Depth increases downward. All properties and fluxes are evaluated per
unit horizontal area.

Companion input definitions: `data_contract.md`. Companion reporting:
`report_contract.md`.

---

## Geometry and sign convention

- Cell \(i\) occupies \([\texttt{top\_depth\_m},\, \texttt{bottom\_depth\_m}]\).
- Positive conductive flux is **downward**.
- Surface energy flux into the column is positive when net energy enters the
  uppermost cell from above.
- Geothermal flux in `illumination_cases.csv` is the **upward** basal heat flux;
  the downward basal boundary flux is therefore its negation. In the last-cell
  residual this means `q_bottom = -geothermal_flux_w_m2`, so the balance term
  `q_top - q_bottom` includes a positive geothermal contribution. Do not impose
  a fixed-temperature, zero-gradient, or ghost-cell basal condition in addition
  to this flux.

---

## Material properties

Heat capacity, cell energy, and conductivity follow `data_contract.md`:

\[
c_p(T) = c_0 + c_1 T + c_2 T^2
\]

\[
E_i(T) = \rho_i \Delta z_i \bigl(c_0 T + \tfrac12 c_1 T^2 + \tfrac13 c_2 T^3\bigr)
\]

\[
k_i(T,z_i) =
\texttt{conductivity\_scale}\,
k_{\mathrm{contact}}
\bigl(1 + \gamma z_i\bigr)
+ k_{\mathrm{rad}} T^3
\]

with \(z_i = \texttt{depth\_center\_m} = 0.5(\texttt{top\_depth\_m}+\texttt{bottom\_depth\_m})\)
and \(\gamma =\) `conductivity_depth_gradient_per_m`.

Evaluate a **fresh** \(k_i\) for every cell on every nonlinear iteration. Do not
reuse one conductivity for the whole column: when \(\gamma \neq 0\), deeper cells
must have a larger contact contribution than shallow cells at the same
temperature. The factor \((1 + \gamma z_i)\) multiplies the contact term only;
it does not scale \(k_{\mathrm{rad}} T^3\).

Effective albedo:

\[
A_{\mathrm{eff}} = \mathrm{clamp}(A_{\mathrm{surface}} + \texttt{albedo\_offset},\, 0,\, 1)
\]

---

## Interior face flux (thermal resistance form)

Between cells \(i\) and \(i+1\), let \(z_f\) be the shared face depth
(`bottom_depth_m` of cell \(i`). Define half-distances:

\[
d_i = z_f - z_i,\qquad d_{i+1} = z_{i+1} - z_f
\]

Face flux (positive downward):

\[
q_{i+1/2}
=
\frac{T_i - T_{i+1}}{
  d_i / k_i(T_i, z_i)
  +
  d_{i+1} / k_{i+1}(T_{i+1}, z_{i+1})
}
\]

Conductivities are evaluated at the **new** time level temperatures.

---

## Surface boundary

Absorbed solar flux \(q_{\mathrm{solar}}\) follows `data_contract.md` (incidence
clipping and eclipse transmission).

Emitted thermal flux:

\[
q_{\mathrm{emit}} = \varepsilon\,\sigma\, T_{\mathrm{surface}}^4
\]

Net downward surface flux into the column:

\[
q_{\mathrm{surface,down}} = q_{\mathrm{solar}} - \varepsilon\,\sigma\, T_{\mathrm{surface}}^4
\]

where \(\varepsilon\) is `surface_emissivity`, \(\sigma\) is
`stefan_boltzmann_w_m2_k4`, and \(T_{\mathrm{surface}}\) is the temperature of
cell index `0` at the new time level.

The surface boundary always uses the material emissivity. Emissivity zero is the
only public way to disable surface radiation. Positive emissivity is never
ignored because a numerical spin-up tolerance is small.

---

## Basal boundary

\[
q_{\mathrm{bottom,down}} = -\texttt{geothermal\_flux\_w\_m2}
\]

Insulating the base (`q_{\mathrm{bottom,down}} = 0`) is correct **only** when
`geothermal_flux_w_m2 == 0`. Whenever the case geothermal is nonzero, the deepest
cell must inject that upward flux through the Neumann identity above.

Expanded deepest-cell residual (`i = N-1`):

```text
r_{N-1} = (E_new - E_old)/dt - (q_top_face - q_bottom_down)
        = (E_new - E_old)/dt - (q_top_face + geothermal_flux_w_m2)
```

### One-cell analytic check

With `cell_count = 1`, `surface_emissivity = 0`, `solar_flux_w_m2 = 0`,
constant \(c_p = c_0\), and `radiative_conductivity_w_m_k4 = 0`, after \(N\)
equal steps of size \(\Delta t\):

\[
T_N = T_0 + N\,\frac{\texttt{geothermal\_flux\_w\_m2}\,\Delta t}{\rho\, c_0\, \Delta z}
\]

because \(q_{\mathrm{surface,down}} = 0\) and
\(q_{\mathrm{bottom,down}} = -G\), so the net power into the cell is \(+G\).
When `maximum_spinup_cycles = 1` and spin-up always runs exactly one unrecorded
period before the report period, \(N = 2\cdot\mathrm{round}(\texttt{period\_s}/\texttt{time\_step\_s})\).

---

## Backward Euler energy balance

For each cell \(i\), with \(\Delta t = \texttt{time\_step\_s}\):

\[
\frac{E_i(T_i^{\mathrm{new}}) - E_i(T_i^{\mathrm{old}})}{\Delta t}
=
q_{\mathrm{top}}^{\mathrm{new}} - q_{\mathrm{bottom}}^{\mathrm{new}}
\]

where

- for \(i = 0\): \(q_{\mathrm{top}} = q_{\mathrm{surface,down}}\);
- for \(i > 0\): \(q_{\mathrm{top}} = q_{(i-1)+1/2}\);
- for \(i = N-1\): \(q_{\mathrm{bottom}} = q_{\mathrm{bottom,down}}\);
- for \(i < N-1\): \(q_{\mathrm{bottom}} = q_{i+1/2}\).

All nonlinear properties (heat capacity / energy, conductivity, radiation,
solar absorption with the active albedo offset) are evaluated at the **new**
time.

Residual for cell \(i\):

\[
r_i =
\frac{E_i(T_i^{\mathrm{new}}) - E_i(T_i^{\mathrm{old}})}{\Delta t}
-
\bigl(q_{\mathrm{top}}^{\mathrm{new}} - q_{\mathrm{bottom}}^{\mathrm{new}}\bigr)
\]

A step is converged when

\[
\max_i |r_i| \le \texttt{nonlinear\_residual\_tolerance\_w\_m2}
\]

within at most `nonlinear_max_iterations` iterations.

Any deterministic nonlinear method that meets the public tolerances is
acceptable (Newton with line search, damped Picard, etc.). Exact iteration
counts, Jacobians, and damping sequences are **not** normative.

Temperatures must remain finite and inside
`[minimum_temperature_k, maximum_temperature_k]`. Violations are fatal.

---

## Periodic spin-up

For each forward case, spin-up follows this exact public order:

```text
state = initial profile from depth_grid.csv
spinup_cycles = 0
converged = false

while spinup_cycles < maximum_spinup_cycles:
    period_start = state
    state = simulate_one_complete_period(state)
    spinup_cycles += 1
    cycle_difference = max_abs(state - period_start)

    if cycle_difference <= spinup_tolerance_k:
        converged = true
        break

if not converged:
    fatal failure

report_state = simulate_one_additional_period(state)
```

Do not replace the grid initial temperatures with a separate steady-state solve
before this loop. Spin-up itself is the only public path from the initial
profile to a periodic state.

Exact rules:

- The first simulated period is cycle 1 and is immediately eligible for the
  convergence check.
- The `maximum_spinup_cycles`-th period is checked before fatal failure.
- Report rows come only from the additional report period after convergence.
- Spin-up steps are not emitted and do not consume report `step_index` values.
- An invariant zero-forcing / no-emission profile converges after one cycle.

Forcing details for each simulated period:

- Use \(N_{\mathrm{steps}} = \mathrm{round}(\texttt{period\_s}/\texttt{time\_step\_s})\)
  equal steps of size `time_step_s`.
- Forcing times are local times within \([0, \texttt{period\_s}]\); each
  nonlinear step evaluates forcing at the **end** of the step.
- The cycle difference is the maximum absolute cell temperature difference
  between period end and period start.

An insufficient-spinup fixture must exit nonzero and leave no final report.

---

## Energy accounting (report period)

For each accepted report-period step:

\[
\Delta E_{\mathrm{stored}}
=
\sum_i \bigl[E_i(T_i^{\mathrm{new}}) - E_i(T_i^{\mathrm{old}})\bigr]
\]

\[
E_{\mathrm{boundary}}
=
\Delta t \bigl(q_{\mathrm{surface,down}} - q_{\mathrm{bottom,down}}\bigr)
\]

\[
E_{\mathrm{residual}}
=
\Delta E_{\mathrm{stored}} - E_{\mathrm{boundary}}
\]

These quantities populate `surface_flux_rows` fields
`stored_energy_change_j_m2`, `net_boundary_energy_j_m2`, and
`energy_residual_j_m2` respectively. Signs must match this convention exactly.

---

## Surface flux row companion quantities

At each report step end time, also record:

| Field | Value |
|-------|-------|
| `absorbed_solar_flux_w_m2` | \(q_{\mathrm{solar}}\) |
| `emitted_thermal_flux_w_m2` | \(\varepsilon\sigma T_0^4\) |
| `conductive_flux_down_w_m2` | Face flux \(q_{1/2}\) between cells 0 and 1 (zero if only one cell) |
| `geothermal_flux_up_w_m2` | `geothermal_flux_w_m2` from the case |

---

## Fatal thermal conditions

Treat as fatal (see `failure_contract.md`):

- non-finite temperatures or residuals;
- temperatures outside the configured limits after a step;
- nonlinear residual not converging within `nonlinear_max_iterations`;
- spin-up failing to meet `spinup_tolerance_k` within `maximum_spinup_cycles`;
- energy residual magnitude exceeding `energy_balance_tolerance_j_m2` on an
  accepted report step when the implementation chooses to enforce that check
  (baseline fixtures remain within tolerance when the model is correct).


## Numerical equivalence

The verifier accepts mathematically equivalent implicit solvers. Candidate
profiles are compared using tolerances that account for different converged
Newton/Picard trajectories. Implementations must satisfy the documented energy
residual and temperature bounds; they are not required to reproduce a hidden
Jacobian, finite-difference increment, or iteration order.
