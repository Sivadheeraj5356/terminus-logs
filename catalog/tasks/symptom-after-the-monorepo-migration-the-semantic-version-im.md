# Symptom: after the monorepo migration the semantic version impact simulator unde

Submission: `c7a7e66b-acc0-4938-80eb-4ed104febadb`  
Slug: `symptom-after-the-monorepo-migration-the-semantic-version-im`  
Latest archive: `c7a7e66b-acc0-4938-80eb-4ed104febadb_submission_2026-07-16T11_45_52.796Z.zip`  
Revisions: 3

## Task summary

Symptom: after the monorepo migration the semantic version impact simulator under /app misreports how proposed upgrades propagate across twenty interconnected release graphs project_01 through project_20 in /app/release-graphs. The svis binary at /app/build/svis and report at /app/build/impact_report.json no longer match independent grading replay per independent_replay and verifier_rules. Repair only /app/impact-engine/main.go, /app/propagation/semver/compare.go, and /app/propagation/simulate/propagate.go. Do not modify /app/Makefile, /app/go.mod, /app/semver-spec, /app/release-graphs, /app/probe-scripts, /app/contracts, or /opt/svis-fixtures. All normative verifier rules live only in the named JSON specs. Read /app/semver-spec/propagation_rules.json for edit_scope inputs outputs build_commands grading grading_fixtures runtime_swap semver range_operators bump_types simulation defaults_from_project_number_n risk_score package_tier status_rule upgrade_order packages_impacted emit_formats output_json main_go_contract immutability deterministic_output independent_replay and verifier_rules. Read /app/semver-spec/report_schema.json for project_keys_order package_impact_keys_order output_json raw_json_key_order status_values tier_values build_outputs and main_go_contract. Project status follows status_rule order BLOCKED then RISK then SAFE. Optional required false edges never emit constraint_violations. Peer edge_type peer never emit constraint_violations never set BLOCKED and only raise peer_mismatch. Propagation path status_token must be exactly lowercase blocked....

Required artifacts include: `/app/release-graphs`, `/app/build/svis`, `/app/build/impact_report.json`, `/app/impact-engine/main.go`, `/app/propagation/semver/compare.go`, `/app/propagation/simulate/propagate.go`, `/app/Makefile`, `/app/go.mod`.

Author anonymous tagged this **medium** build-and-dependency-management task (build-and-dependency-management, semantic-versioning, dependency-graph, semver, debugging).

Time estimates: expert ~180.0 min, junior ~360.0 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `c7a7e66b-acc0-4938-80eb-4ed104febadb_submission_2026-07-16T11_45_52.796Z.zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
