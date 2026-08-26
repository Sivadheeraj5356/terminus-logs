# Passenger rebooking build graph stitchers must compile cancellation-to-replaceme

Submission: `3b4836cb-00ab-4b87-9066-191d521b2c1e`  
Slug: `passenger-rebooking-build-graph-stitchers-must-compile-cance`  
Latest archive: `3b4836cb-00ab-4b87-9066-191d521b2c1e_submission_2026-07-18T18_22_51.566Z.zip`  
Revisions in Dropbox: 4

## Task summary

Passenger rebooking build graph stitchers must compile cancellation-to-replacement depends_on edges and seat-inventory closures into staged layer manifests, then publish digest-sealed build ledgers that operations can trust without rebuilding the dependency graph from live inputs. Shipped compile and publish stages do not match the dependency graph, manifest digest, and export contracts below. Inputs live under /app/data/ (passengers.json, flight-cancellations.json, seat-inventory.json, alliance-agreements.json, airline-policies.json). Compile writes /app/state/rebooking-snapshot.json and /app/state/rebooking-ledger.json. Publish writes /app/output/rebooking-plan.json and /app/output/passenger-summary.json from those staged artifacts only and must never reload /app/data/. Invoke /app/bin/passenger-rebooking-engine after producing it with /app/scripts/build.sh. Subcommands are build, stage, export, and version; no arguments means build; build means stage then export; version prints passenger-rebooking-engine/1.0.0; export exits 2 when snapshot or ledger is missing. TB3_DATA_DIR, TB3_STATE_DIR, and TB3_OUTPUT_DIR override those roots only when set to absolute paths; relative TB3_DATA_DIR is ignored. Collapse same-flight_id cancellations by highest revision, then lexicographically smallest event_id. Derive cancelled_flights, collapsed_cancellation_count, and disruption_date from that collapsed set. Score passengers as loyalty weight plus fare_class weight; when priority_pick_mode is priority_score, process by descending score then ascending passenger_id; when it is...

Required artifacts include: `/app/data/`, `/app/state/rebooking-snapshot.json`, `/app/state/rebooking-ledger.json`, `/app/output/rebooking-plan.json`, `/app/output/passenger-summary.json`, `/app/bin/passenger-rebooking-engine`, `/app/scripts/build.sh`, `/app/docs/`.

Author mohit tagged this **hard** build-and-dependency-management task (build-graph, dependency-graph, manifest-digest, graph-stitch, build-ledger).

Time estimates: expert ~90 min, junior ~180 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `3b4836cb-00ab-4b87-9066-191d521b2c1e_submission_2026-07-18T18_22_51.566Z.zip` is a task submission, not a Harbor job. 4 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Dependency plan looks consistent locally but violates a hidden pin/conflict rule.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
