# Surface-enrichment correction

XRF reports surface mass fractions (f_Au_s, f_Ag_s, f_Cu_s) ± σ_xrf. Aged silver-alloy coins exhibit silver bloom: surface silver (and sometimes gold) is enriched relative to bulk while surface copper is depleted. Enrichment never reverses those directions.

## Enrichment depth

Each coin references enrichment_model_id in /app/data/enrichment-models.json. Compute:

δ = min(enrichment_cap, rate_per_year * burial_years)

using that model's parameters only. Never apply a fleet-wide default when a coin names a model.

## Directional bulk bounds (with measurement noise)

k_sigma is from assay-config.json (default 1.0).

- Silver: bulk Ag cannot exceed surface Ag beyond noise, and may be lower by up to δ:
  - f_Ag_bulk_max = min(1, f_Ag_s + k_sigma * σ_xrf)
  - f_Ag_bulk_min = max(0, f_Ag_s − δ − k_sigma * σ_xrf)
- Gold: same directional shape as silver:
  - f_Au_bulk_max = min(1, f_Au_s + k_sigma * σ_xrf)
  - f_Au_bulk_min = max(0, f_Au_s − δ − k_sigma * σ_xrf)
- Copper: surface depletion implies bulk Cu is at least surface Cu (minus noise) and may be higher by up to δ:
  - f_Cu_bulk_min = max(0, f_Cu_s − k_sigma * σ_xrf)
  - f_Cu_bulk_max = min(1, f_Cu_s + δ + k_sigma * σ_xrf)

Do not apply symmetric ±δ about the surface reading for all three metals.
