# Staging cost model (finance worksheet)

**Approved for Burgers FV consumable staging.** Use this worksheet unless procurement posts a superseding memo.

- Purchases: `sum c[p,t]*q[p,t]`
- Fleet: owned trucks `A*K` plus `F * max(0, runs[t]-K)` each week (per overflow run)
- Holding: `h * sum_p v[p]*inv[p,t]` on all end-of-week stock
- Peak: `S * (vol[t] - PeakV)` when `vol[t] > PeakV`
- Shockwave window: `W * vol[t]` when `shockwave[t]=1`

Runs: sum over kits of `ceil(v[p]*q[p,t]/B)`.

See `/app/facilities/finance_index.md`.
