# cold cap policy

Habitat cold_cap_m3 limits total cold-chain cargo volume assigned to berths.

After berth assignments are complete:

```
cold_m3_used = sum(m3 for each assignment where cold is true)
cold_cap_ok = cold_m3_used <= cold_cap_m3 + 1e-9
```

Round cold_m3_used to six decimal places on berth-staging.json.

When cold_cap_ok is false, set feasible to false on berth-staging.json.

Export must refuse when cold_cap_ok is false on berth-staging.json. Reading cold_cap_ok only from export-bind.json is insufficient.

Only assignments with cold true contribute to cold_m3_used. Non-cold cargo m3 is excluded.
