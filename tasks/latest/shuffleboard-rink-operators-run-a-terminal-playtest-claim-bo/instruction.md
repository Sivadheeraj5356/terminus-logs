Shuffleboard rink operators run a terminal playtest claim board under /app. The simulated court already loads layouts and wax-lot manifests. Your job is to finish the combinatorial planner so exclusive wax lanes are allotted under friction-band game rules and a sealed claim ledger is published for playtest review.

The simulator must chalk an intermediate slate, then allot from that slate alone, and emit a deterministic claim ledger for the simulated match window. Contracts live in /app/docs/wax-lane-contract.md, /app/docs/chalk-slate.md, and /app/docs/cli-surface.md. Sample court fixtures live at these absolute paths:

- /app/data/rink-lanes.json
- /app/data/disk-packages.json

Deliverables:

- Working CLI /app/bin/waxlane-allot (rebuild after source edits)
- Intermediate chalk slate as specified in the chalk-slate doc
- Final claim ledger at /app/output/wax-lane-claim-ledger.json matching the wax-lane contract

Absolute paths only. Do not invent flags or schema fields beyond the cited docs.

Independent playtest correlation may use hashlib digests and match geometry against /app/docs contracts.
