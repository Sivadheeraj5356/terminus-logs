# Density-constraint band

Given measured density ρ_m ± σ_ρ (one-sigma half-width), a composition f is inside the density band when:

|ρ(f) − ρ_m| ≤ σ_ρ

where ρ(f) uses the coin's mixing rule.

Parameterize the simplex by free variables (f_Au, f_Ag) with f_Cu = 1 − f_Au − f_Ag ≥ 0. The set of compositions satisfying the inequality is a closed band around the iso-density curve. Report the band as axis-aligned bounds over compositions that pass a dense grid sample of the simplex (grid_n from assay-config.json), including compositions that touch simplex boundaries (for example f_Cu = 0).

Wide bands that span nearly the entire simplex are valid results when σ_ρ is large; they are not errors.
