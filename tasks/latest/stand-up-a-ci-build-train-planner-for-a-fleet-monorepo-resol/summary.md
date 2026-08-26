# Stand up a CI build-train planner for a Fleet monorepo: resolve module DAG order

- **UUID:** `82611389-a8ee-445d-bcbd-094b15652630`
- **Slug:** `stand-up-a-ci-build-train-planner-for-a-fleet-monorepo-resol`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

Stand up a CI build-train planner for a Fleet monorepo: resolve module DAG order, gate semver floors and registry approval, and publish compliance artifacts for release engineering. Your deliverable is the fleetd HTTP planner plus the emit-fleet-build-audit.sh build-train driver.

fleetd reads CSV module manifests, computes a stable topological build sequence, enforces policy from /app/config/fleet-policy.toml on every request, and exposes plans at POST /v1/build-plan plus plan seals at POST /v1/build-attest. The driver script reads /app/fixtures/fleet-release.pin, probes the live API including build-attest, rewrites policy to secure defaults, writes a compact probe snapshot to FLEET_STAGE_ROOT (default /app/var/fleet-stage) as /app/var/fleet-stage/build-train-probe.json, appends run-journal.jsonl, then exports /app/output/fleet-build-compliance.json.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
