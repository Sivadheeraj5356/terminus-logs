# Blend feasibility certificate contract

## Output path

/app/output/blend-feasibility-cert.json

## Certificate body (before digest fields)

- cert_version: JSON string "1.0" (not a numeric 1.0)
- batch_generation from allocation
- allocation_rows: spec_id, priority, feasible, total_cost, lot_amounts_ml per solution
- summary: feasible_count, infeasible_count, total_cost (sum of feasible total_cost, round6)

## Three-layer digest

Sorted-key compact JSON serialization uses recursively sorted object keys (matching JsonCodec).

For allocation and dual layers, hash the exact UTF-8 text of the on-disk state files /app/state/allocation.json and /app/state/dual-certificate.json as written by prior stages (compact JSON via JsonCodec.write, no trailing newline). Do not re-serialize from in-memory objects, which can change float formatting.

1. allocation layer: SHA-256 of the on-disk allocation.json bytes
2. dual layer: SHA-256 of the on-disk dual-certificate.json bytes
3. combined layer: SHA-256 of sorted-key compact JSON of the certificate body above (without feasibility_digest or digest_layers)

feasibility_digest = SHA-256( allocation_layer + "|" + dual_layer + "|" + combined_layer )

digest_layers object exposes allocation, dual, and combined hex digests.

## Seal inputs

seal reads allocation.json and dual-certificate.json only. It must not read blend-model.json or live input files.
