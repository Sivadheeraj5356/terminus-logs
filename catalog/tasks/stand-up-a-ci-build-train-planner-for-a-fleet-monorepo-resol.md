# Stand up a CI build-train planner for a Fleet monorepo: resolve module DAG order

Submission: `82611389-a8ee-445d-bcbd-094b15652630`  
Slug: `stand-up-a-ci-build-train-planner-for-a-fleet-monorepo-resol`  
Latest archive: `82611389-a8ee-445d-bcbd-094b15652630_submission_2026-07-17T04_04_13.104Z.zip`  
Revisions in Dropbox: 1

## Task summary

Stand up a CI build-train planner for a Fleet monorepo: resolve module DAG order, gate semver floors and registry approval, and publish compliance artifacts for release engineering. Your deliverable is the fleetd HTTP planner plus the emit-fleet-build-audit.sh build-train driver. fleetd reads CSV module manifests, computes a stable topological build sequence, enforces policy from /app/config/fleet-policy.toml on every request, and exposes plans at POST /v1/build-plan plus plan seals at POST /v1/build-attest. The driver script reads /app/fixtures/fleet-release.pin, probes the live API including build-attest, rewrites policy to secure defaults, writes a compact probe snapshot to FLEET_STAGE_ROOT (default /app/var/fleet-stage) as /app/var/fleet-stage/build-train-probe.json, appends run-journal.jsonl, then exports /app/output/fleet-build-compliance.json.

Required artifacts include: `/app/config/fleet-policy.toml`, `/app/fixtures/fleet-release.pin`, `/app/var/fleet-stage`, `/app/var/fleet-stage/build-train-probe.json`, `/app/output/fleet-build-compliance.json`, `/app/docs/fleet-http-contract.md`, `/app/docs/build-graph-spec.md`, `/app/docs/module-fixture-index.md`.

Author anonymous tagged this **hard** build-and-dependency-management task (go, monorepo, build-graph, semver, fleet-release).

Time estimates: expert ~180 min, junior ~360 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `82611389-a8ee-445d-bcbd-094b15652630_submission_2026-07-17T04_04_13.104Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
