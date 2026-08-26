# Feasibility intersection

A composition f is feasible when it lies in the density band and satisfies the corrected XRF bulk bounds for Au, Ag, and Cu simultaneously, and f_Au + f_Ag + f_Cu = 1 with each ≥ 0.

Sample the simplex on the same grid as the density band. Collect all grid points that pass both constraints.

- If the collected set is non-empty: status = "feasible". Report region bounds as min/max of f_Au, f_Ag, f_Cu over the collected points (a region, never a single centroid or mode).
- If empty: status = "inconsistent".

Boundary points (any fraction exactly 0) that satisfy both constraints must be included when the grid lands on them; do not reject them for numerical instability.
