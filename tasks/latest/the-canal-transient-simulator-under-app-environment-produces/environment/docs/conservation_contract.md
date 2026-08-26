Track initial_total_storage_m3, cumulative_external_volume_m3, current_total_storage_m3, mass_residual_m3.

External contributions: node inflows/withdrawals, flows on storage-boundary links, and volume impulses. Internal storage-to-storage flows cancel.

Per committed half step:
external_delta = half_dt * (sum active external inflows + sum boundary exchanges entering the storage network)
using converged midpoint link flows. Impulses add exactly at their event time.

mass_residual = current_total_storage - initial_total_storage - cumulative_external_volume
Computed from unrounded internals. Report fields are rounded; maximum residual diagnostics use unrounded residuals.
