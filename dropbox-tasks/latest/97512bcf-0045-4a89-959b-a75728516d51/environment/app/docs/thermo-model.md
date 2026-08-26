# Binary cryogenic chamber model

Closed N2/He vessel. Normative sources: this document, `/app/docs/schema.json`, `/app/config/species.json`, `/app/config/chamber.toml`, and the calibration NDJSON supplied at runtime. File order in the calibration stream is not authoritative. NDJSON lines may use LF or CRLF; trailing `\r` must be stripped before parse. Blank and whitespace-only lines are ignored.

## Free volume and Van der Waals mixture

Condensate displaces free gas volume. EOS work always uses `V_free`, never the geometric vessel volume alone:

```text
V_free = max(V * vmin_frac, V - kappa_film * n_cond_n2)
```

`kappa_film` and `vmin_frac` are N2 fields in `species.json`.

With free-gas inventories \(n_1\) (N2), \(n_2\) (He), \(n=n_1+n_2\), \(x_i=n_i/n\):

```text
a_mix = x1^2 a1 + x2^2 a2 + 2 x1 x2 sqrt(a1 a2)   # Lorentz–Berthelot geometric cross term
b_mix = x1 b1 + x2 b2
P = n R T / (V_free - n b_mix) - a_mix n^2 / V_free^2
R = 8.314 J/(mol·K)
p_i = x_i P
```

Reported `p_total` must agree with this EOS on the final free-gas state within relative 0.1%.

## Thermal leg

Stations after the first compare temperature to the previous station:

- cooler → descend (`thermal_leg` 0)
- warmer → ascend (`thermal_leg` 1)
- equal → reuse the previous station's leg

The first station is descend.

## Temperature-banded Langmuir authority (fresh resolve)

NDJSON rows carry `seq`, `K_n2`, `K_he`, `n_sites`, and either `"universal": true` or bounds `t_min`/`t_max`. Bounds are **inclusive** on both ends. Optional `leg` is `"descend"`, `"ascend"`, or omitted (any leg). Optional `requires_prev_seq` (integer) admits the row only when the previous station's applied `cal_seq` equals that value; absent field means no predecessor gate. On the first station the predecessor is treated as missing (`-1`), so gated rows cannot win.

A row is valid only if `K_n2 > 0`, `K_he >= 0`, and `n_sites > 0`. Invalid rows are retained in the table but never compete.

Fresh resolve at temperature `T`, leg `L`, previous `cal_seq` `S_prev`:

1. Candidates = valid **bounded** rows covering `T` whose `leg` is omitted or equals `L`, and whose `requires_prev_seq` is absent or equals `S_prev`. Universals are excluded from this set.
2. If any candidates: pick highest `seq`, then narrowest `(t_max - t_min)`, then largest `n_sites`, then lowest `t_min`.
3. Else candidates = valid universal rows; pick highest `seq`, then largest `n_sites`.
4. Else fail.

## Sticky calibration (any-leg / universal only)

The chamber remembers the last selected `seq` as sticky state.

Rows with an explicit `"leg"` are never sticky-reused: every station fresh-resolves while they are in play.

Any-leg bounded rows (`leg` omitted) and universal rows may sticky-reuse when still eligible:

- the sticky row remains valid, and
- if bounded any-leg: `t_min <= T <= t_max`, or
- if universal: no valid bounded row covers `(T, L)` under the fresh rules (including `requires_prev_seq`).

When sticky remains eligible, keep that `seq` even if a short higher-`seq` overlay also covers `T`. Otherwise fresh-resolve and replace sticky. When looking up sticky parameters for a duplicated `seq`, use the same narrowest-window tie-break as fresh resolve.

## Condensate footprint

```text
n_sites_eff = max(0, n_sites - film_site_beta * n_cond_n2)
```

`film_site_beta` is the N2 species field.

## Fugacity-driven competitive Langmuir and wall locks

Driving forces are fugacities, not raw partial pressures:

```text
f_i = p_i * exp(b_i * P / (R T))
theta_i = K_i f_i / (1 + K_N2 f_N2 + K_He f_He)
n_ads_i = n_sites_eff * theta_i
```

Usual path: return adsorbate to free gas, then re-equilibrate.

While frozen, nitrogen adsorbate is locked. Helium still re-equilibrates on residual sites:

```text
n_sites_eff = max(0, n_sites - film_site_beta * n_cond_n2 - n_ads_n2)
```

Thaw wall-hold: on the station where the chamber leaves the frozen state, nitrogen adsorbate stays locked for that entire station (helium and condensate follow unfrozen / thaw rules). Hold ends when the station completes.

Helium never enters bulk condensate. Sealed mole ledgers close at every station: N2 across gas+ads+condensate, He across gas+ads.

## Condensation and freeze hysteresis

For `T < T_cond`, drive nitrogen partial pressure (from the `V_free` EOS) to `P_vap(T)` by condensing or evaporating, except frozen films must not lose condensate.

```text
P_vap(T) = P_vap_ref * exp(-L_vap/R * (1/T - 1/T_vap_ref))
```

Enter freeze when condensate exists and `T <= T_freeze`. Leave freeze only when `T >= T_thaw` (do not thaw on `T_freeze`).

### Normative N2 plant constants (`/app/config/species.json`)

Shipped config may drift; restore these exact N2 fields (other species fields stay as shipped if already correct):

```text
T_freeze = 63.15 K
T_thaw   = 68.0 K
film_site_beta = 0.012
kappa_film = 0.00045
vmin_frac = 0.08
```

## Coupled station solver

Limits come from `/app/config/chamber.toml`: `max_solver_iters`, `ads_tol`, `cond_tol`.

### Normative solver limits (`/app/config/chamber.toml`)

```text
max_solver_iters = 48
ads_tol = 1.0e-10
cond_tol = 1.0e-10
```

Per station: determine thermal leg; apply sticky or fresh Langmuir resolve (passing previous station `cal_seq`); then iterate up to `max_solver_iters` times — Langmuir (honoring freeze / thaw wall-hold) then condensation/hysteresis, recomputing `V_free` as condensate changes — until `|Δn_ads_n2|+|Δn_ads_he| < ads_tol` and `|Δn_cond_n2| < cond_tol`. Emit inventories, `cal_seq`, `solver_iters`, `thermal_leg` (`0`/`1`), and regime. Reported `p_total` must match the final free-gas inventories on `V_free`.

Count `condensation_events` when a station ends with more condensate than it started; `freeze_events` when it ends frozen after starting unfrozen.

## Operator interface

```text
/app/bin/cryovac [--profile PATH] [--calibration PATH] [--out PATH] [--volume M3]
```

Defaults: `/app/data/profiles/n2_he_cooldown.json`, `/app/data/calibration/sorption_cal.ndjson`, `/app/vacuum_simulation.json`, `0.012` m³.

Unknown flags, incomplete flag/value pairs, repeated flags, and non-positive `--volume` are fatal: exit code 2, empty stdout. Successful runs exit 0.
