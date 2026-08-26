# Rebuild the stub engine under /app/keyshare_engine into the witness binary at /a

Submission: `be7ed9f0-4c00-4873-b43c-f398c9247298`  
Slug: `rebuild-the-stub-engine-under-app-keyshare-engine-into-the-w`  
Latest archive: `be7ed9f0-4c00-4873-b43c-f398c9247298_submission_2026-07-09T04_11_53.288Z.zip`  
Revisions: 2

## Task summary

Rebuild the stub engine under /app/keyshare_engine into the witness binary at /app/bin/keyshare_witness so one run merges the three shards under /app/data/handshake_capture in time order, walks each observation through the gate ladder type, required, empty offered, service, banned or rescued, duplicate, quota, rate, then phase with strength, and writes the report to /app/output/expected.json. A rerun must reproduce identical bytes and leave every shard untouched. Each line carries observation_id, service_id, observed_ts_ns, offered_groups, client_id. A wrongly typed field earns REJECTED_TYPE, a missing field INVALID. The report holds four top level keys decisions, by_service, by_verdict, summary. Each decision row carries observation_id, service_id, verdict, matched_group. The fifteen verdicts are HYBRID_PQ_OK, CLASSIC_OK, DEPRECATED_GRACE, PRE_ROLLOUT_PASS, SEAL_RESCUED, RATE_LIMITED, POLICY_DOWNGRADE_BLOCKED, INSUFFICIENT_STRENGTH, DUPLICATE_OBSERVATION, QUOTA_EXHAUSTED, GROUP_BANNED, UNKNOWN_SERVICE, NO_GROUPS_OFFERED, REJECTED_TYPE, INVALID. Every detail — admit class membership, summary fields including report_digest, the decision sort chain over severity plus service_id, observed_ts_ns and observation_id, digest recipe, gate order and per gate flags — lives in /app/data/admission_policy/output_envelope.json.

Required artifacts include: `/app/keyshare_engine`, `/app/bin/keyshare_witness`, `/app/data/handshake_capture`, `/app/output/expected.json`, `/app/data/admission_policy/output_envelope.json`.

Author anonymous tagged this **hard** security task (tls, post-quantum, key-exchange, policy, go, hmac).

Time estimates: expert ~90 min, junior ~240 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `be7ed9f0-4c00-4873-b43c-f398c9247298_submission_2026-07-09T04_11_53.288Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
