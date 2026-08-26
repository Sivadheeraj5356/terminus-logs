# Missing-data policy

Per coin:

- If measured density is missing (null) or density uncertainty is missing: status = "insufficient_data", reason = "missing_density". Do not invent a density.
- If XRF surface fractions are missing (null) but density is present: compute the density band alone; status = "density_only"; report that band as the feasible region; leave XRF-derived bounds null in the derivation trace.
- If XRF uncertainty is missing while XRF fractions are present: status = "insufficient_data", reason = "missing_xrf_uncertainty".
- Never silently replace missing numeric fields with 0 or any placeholder fraction.
