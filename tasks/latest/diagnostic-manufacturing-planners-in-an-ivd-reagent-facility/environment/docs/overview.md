# Reagent lot blend feasibility certificate

Diagnostic manufacturing planners run the blendcert CLI under /app to bind reagent lot inputs, solve least-cost blend allocations, certify LP dual prices, and seal a three-layer feasibility certificate for quality audit.

## CLI

Run java -jar /app/target/blendcert.jar with subcommands bind, solve, certify, and seal.

Exit codes: 0 success, 2 missing state artifact, 3 bad input or unknown subcommand.

Missing files under /app/input during bind (for example lots.json or specs.json absent) are bad input and must exit 3.

Missing files under /app/state required by the current stage (for example blend-model.json, lot-inventory.json, allocation.json, or dual-certificate.json) are missing state artifacts and must exit 2.

## Stages

1. bind reads /app/input/lots.json and /app/input/specs.json and writes /app/state/blend-model.json and /app/state/lot-inventory.json
2. solve reads blend-model and lot-inventory, debits remaining lot volume per specification in model order, and writes /app/state/allocation.json plus /app/output/blend-ledger.json
3. certify reads blend-model and allocation and writes /app/state/dual-certificate.json including model_layer_digest
4. seal reads allocation and dual-certificate only and writes /app/output/blend-feasibility-cert.json

## Paths

State under /app/state. Outputs under /app/output. Contracts in sibling docs under /app/docs.

## Implementation boundaries

blendcert stages must not read /tests, /opt/verifier-fixtures, or other verifier-only paths. Digest layers must hash the on-disk state file bytes written by prior stages as defined in blend-feasibility-cert-contract.md and dual-price-certificate.md.

## Optional greedy preview (decoy)

When environment variable BLEND_GREEDY_PREVIEW is exactly 1, solve may write /app/state/greedy-preview.json via CostHeuristic using a cheapest-lot-first heuristic per specification. This file is diagnostic only. certify and seal must not read it, and blend-feasibility-cert.json must be identical whether or not BLEND_GREEDY_PREVIEW is set.
