# Status glossary

`FRESH_OK` means authentication seal and authorization latch agree, dual_peak stays closed, and composed deadline matches the frozen absolute window where required. On `burst_cap` it also means occupancy seated at `limit`. On `rot_chain` it means occupancy ended at 3 with dual_peak closed.

`REUSE_HIT` means a prior session generation stayed admit-capable during or after a newer seal (token-reuse / dual-valid privilege failure), including a non-zero dual_peak mid-bundle.

`CAP_HOLD` means occupancy is over the principal RBAC budget, a `burst_cap` row finished below `limit`, or a `rot_chain` row failed to seat three successful admits after stale-fence rejection.

These tokens are authz domain labels, not generic pass/fail flags.
