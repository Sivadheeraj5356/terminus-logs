# Handling

`inv[p,t] = inv[p,t-1] + q[p,t] - d[p,t]` with `inv[p,0]=0`. Meet demand from stock; maintain `inv[p,t] >= smin[p]` every week. Reserves are per kit, not pooled.

Weekly purchased volume for fleet and surcharge rules is `vol[t] = sum_p v[p]*q[p,t]`. End-of-week stock volume for holding is the same weighted sum over `inv[p,t]`, not purchases.

Do not impose terminal inventory equalities; weekly reserves are lower bounds only.
