# Dual price certificate

## Output path

/app/state/dual-certificate.json schema_version dual-certificate/1

## model_layer_digest

SHA-256 hex digest of the exact UTF-8 text of /app/state/blend-model.json as written by bind (compact JSON via JsonCodec.write, no trailing newline). Do not re-hash from an in-memory reconstruction.

## Per-specification certificates

One certificate row per allocation solution:

- certified false when the solution is infeasible (empty shadow_prices, optimality_gap_bound 0.0)
- certified true when feasible with shadow_prices and optimality_gap_bound

## Shadow prices (finite differences)

Shadow prices come from LP finite-difference perturbations on the active constraints at the optimal blend.

epsilon = max(1e-4, target_volume_ml * 1e-4)

- volume: (cost(V + epsilon) - base_cost) / epsilon when feasible
- lots[lot_id]: when amount_ml is at available_ml cap, relax cap by epsilon and compute (base_cost - relaxed_cost) / epsilon, floored at zero
- analytes_lower[analyte]: when concentration is at lower bound, tighten lower by epsilon and compute (tightened_cost - base_cost) / epsilon
- analytes_upper[analyte]: when concentration is at upper bound, relax upper by epsilon and compute (base_cost - relaxed_cost) / epsilon

All shadow price components are rounded to six decimal places.
