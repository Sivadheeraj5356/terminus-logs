# Additional scenario packs

Extra fleet rollout scenarios may be mounted under /opt/verifier-fixtures with the same layout as /app/fixtures/scenarios (meta.json, decisions.jsonl, units.json, dependencies.json, resources.json, topology.json).

## odip-holdout

Path /opt/verifier-fixtures/odip-holdout uses scenario_id holdout_alpha. Decision identifiers include H1, H2, and H3. Region clearance is HOLD-7. Topology parent HU1 fans out to child HU3.

## odip-holdout-seal

Path /opt/verifier-fixtures/odip-holdout-seal uses scenario_id holdout_seal with rollout_epoch 100 and topology_revision seal-rev-omega. It is a single-decision pack (S1) that exercises epoch_seal and bound_lattice_digest fields from /app/docs/rollout-epoch-seal-contract.md.

## odip-holdout-slot

Path /opt/verifier-fixtures/odip-holdout-slot uses scenario_id holdout_slot with decisions W1, W2, and W3 (W2 exclusive). It exercises window_digest and booking_digest fields from /app/docs/booking-window-slot-contract.md.

The lattice and plan must set scenario_id from meta.json for every scenario including holdout_alpha, holdout_seal, and holdout_slot.
