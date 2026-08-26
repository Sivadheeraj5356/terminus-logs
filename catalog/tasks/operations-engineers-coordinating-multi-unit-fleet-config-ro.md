# Operations engineers coordinating multi-unit fleet config rollouts need an opera

Submission: `a3e7ad6a-de78-4c12-b3e5-db135b3a044e`  
Slug: `operations-engineers-coordinating-multi-unit-fleet-config-ro`  
Latest archive: `a3e7ad6a-de78-4c12-b3e5-db135b3a044e_submission_2026-07-20T06_19_33.651Z.zip`  
Revisions: 2

## Task summary

Operations engineers coordinating multi-unit fleet config rollouts need an operational planning workflow that stages an impact lattice and delivers an ordered feasibility plan before daemon rollout windows open. The Go workspace under /app already loads scenario fixtures and builds the odip binary. Extend that baseline so operators can run stage, plan, and run against scenario directories and the shared approval policy file /app/fixtures/policies/approval_policy.json Stage must write the lattice artifact to /app/state/odip/impact_lattice.json before plan runs. Plan must write the feasibility plan to /app/output/decision_impact_plan.json and, on success, append one journal line to /app/state/odip/rollout_journal.jsonl without reopening raw scenario decision files. Plan must consume the staged lattice and policy only. Each artifact must carry the scenario identity from that scenario meta file. Lattice digests are lowercase hex witnesses of the staged fleet snapshot. Plans bind epoch seals, window digests, and booking digests, refuse superseded epochs with exit code 4, and surface topology fan-out, dependency cycles, pool contention, exclusive-window drift, approval stacking, and regional clearance failures as infeasible or conflicted rollouts.

Required artifacts include: `/app/fixtures/policies/approval_policy.json`, `/app/state/odip/impact_lattice.json`, `/app/output/decision_impact_plan.json`, `/app/state/odip/rollout_journal.jsonl`, `/app/bin/odip`, `/app/fixtures/scenarios`, `/app/docs/org-decision-planning-workflow.md`, `/app/docs/dependency-closure-contract.md`.

Author anonymous tagged this **hard** system-administration task (decision-impact, org-planning, dependency-closure, approval-sequence, fleet-feasibility, rollout-planning).

Time estimates: expert ~120 min, junior ~240 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `a3e7ad6a-de78-4c12-b3e5-db135b3a044e_submission_2026-07-20T06_19_33.651Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
