# FV convoy memo

Purchased volume `vol[t] = sum_p v[p]*q[p,t]`. Truck runs `ceil(vol[t]/B)` on **pooled** volume — not per-kit ceils.

Owned trucks: pay `A` once per truck kept for the season (`K` total). Each owned truck covers one run every week at no extra charge. If `runs[t] > K`, pay flat haulier `F` **once** that week (not per overflow run).

Do not use `/app/consumables/truck_policy_v2.md` or `/app/docs/fleet_rules.md`.
