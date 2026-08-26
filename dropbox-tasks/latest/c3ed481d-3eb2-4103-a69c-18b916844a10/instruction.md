Offline aisle traversal learner. Fix the sources under `/app/environment`, rebuild `/app/bin/lane_matrix` from that workspace (see `/app/environment/docs/artifact_rules.md` for the release build invocation), then regenerate `/app/output/coverage_map.json` with the command below.

`/app/bin/lane_matrix --fixtures /app/fixtures --spec /app/spec --out /app/output/coverage_map.json`

Fresh rebuilds from `/app/environment` and that same command are what count. Fixture packs live under `/app/fixtures` (train plus held_out); annex modules under `/app/spec`. Every instance needs a rows array. Each row carries visits, residual_risk, witness, seal_ok, frontier_ids, and cells as defined in artifact_rules.md (including digest_ops binding helpers). Top-level violation_count must stay zero on both splits. Training packs alone are not enough. Hand-written maps are rejected.
