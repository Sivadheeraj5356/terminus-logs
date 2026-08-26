# Rollout epoch seal and journal

Fleet daemons bind each published decision impact plan to the staged lattice digest and the scenario rollout epoch.

## Plan export fields

Every plan at /app/output/decision_impact_plan.json must include:

- rollout_epoch — copied from staged lattice meta
- topology_revision — copied from staged lattice meta
- bound_lattice_digest — equals the staged lattice_digest
- epoch_seal — witness binding lattice digest, epoch, scenario_id, and topology_revision

## Epoch seal formula

epoch_seal is the lowercase hex SHA-256 of this UTF-8 payload:

lattice_digest | rollout_epoch | scenario_id | topology_revision

where | is a single ASCII pipe character and rollout_epoch is decimal without padding.

## Rollout journal

Successful plan writes append one JSON line to /app/state/odip/rollout_journal.jsonl with keys scenario_id, rollout_epoch, plan_digest, lattice_digest, epoch_seal, topology_revision, window_digest, and booking_digest.

## Supersession gate

Before writing a plan, odip loads the latest journal row for the same scenario_id. When a prior row exists, the new rollout_epoch must be strictly greater than the prior rollout_epoch. Equal or older epochs refuse the plan with exit code 4 and must not append a journal line.

Stage remains allowed regardless of journal state. Only plan (and run after stage) enforce supersession.
