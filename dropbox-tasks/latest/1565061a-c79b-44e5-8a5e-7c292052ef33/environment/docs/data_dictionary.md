# Data dictionary

## Core demand fields (starter declares these)

`T`, `P`, `B`, `v[p]`, `d[p,t]`, `c[p,t]`, `smin[p]`

## Additional instance fields (read from `/app/instance.dzn`)

| Field | Type | Role |
|-------|------|------|
| `shockwave[t]` | `array[1..T] of int` | Shock-capture window flag week `t` |
| `F` | `int` | Flat outside-haulier fee per overflow week |
| `A` | `int` | Season cost per owned refrigerated truck |
| `h` | `int` | Holding rate per volume unit above bay |
| `G` | `int` | Covered bay capacity (free holding volume) |
| `PeakV` | `int` | Peak surcharge volume threshold |
| `S` | `int` | Flat peak surcharge per heavy week |
| `W` | `int` | Flat shock-capture bay fee per flagged week with purchases |

## Model surface (verifier structural checks)

Your `/app/model.mzn` must declare and use the instance parameters above, including the identifiers `shockwave`, `PeakV`, `G`, and `W`, and must reference kit volumes `v[p]` when computing weekly purchased volume.

## Modeling notes

- Weekly purchased volume is `vol[t] = sum_p v[p]*q[p,t]`; truck runs are `ceil(vol[t]/B)` on **pooled** volume (not per-kit ceils).
- Choose fleet size `K` as a decision variable in `0..KMAX` and minimize total cost jointly over `K` and all purchases `q[p,t]` in a single solve.
- Overflow hire: when `runs[t] > K`, charge flat `F` **once** that week (not per excess run beyond `K` and not `F * hire[t]` when `hire[t]` counts overflow runs).
- Holding: end-of-week stock volume is `sum_p v[p]*inv[p,t]`; charge `h * max(0, stock_volume - G)` each week.
- Peak: flat `S` once when `vol[t] > PeakV`.
- Shockwave: flat `W` once when `shockwave[t] = 1` and `vol[t] > 0`.
- Inventory: `inv[p,1] = q[p,1] - d[p,1]`; `inv[p,t] = inv[p,t-1] + q[p,t] - d[p,t]` for `t >= 2`; maintain `inv[p,t] >= smin[p]`.
- Bounds: per-kit upper bound `CAP[p] = sum_t d[p,t] + smin[p]` suffices for `q[p,t]` and `inv[p,t]`; set `KMAX = ceil(sum_p v[p]*CAP[p] / B)`.
- Search: run with `chuffed` via `/app/run_model.sh`. If search is slow, branch on `K` before purchase quantities (`int_search` on `K` first).

Costing rules also appear in field memos under `/app/consumables` and `/app/facilities`; reconcile against `/app/facilities/finance_index.md`.
