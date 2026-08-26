# Build-train operations

1. Ensure API is reachable at http://127.0.0.1:8080/health.
2. Read release pin from /app/fixtures/fleet-release.pin.
3. Query approved module count from the module registry JSON store (REGISTRY_DB_PATH, default the module registry file).
4. Validate OpenAPI with curl (/openapi.json must describe /v1/build-plan, /v1/build-attest, and /health).
5. Rewrite /app/config/fleet-policy.toml with secure defaults from /app/docs/fleet-policy-schema.md. Values are unquoted (see that schema for exact formatting).
6. Probe build plan order against the default manifest, confirm debug endpoint returns 404, probe /v1/build-attest for plan_digest and plan_seal, and validate release pin is non-empty.
7. Write probe snapshot /app/var/fleet-stage/build-train-probe.json first (see /app/docs/probe-snapshot-contract.md).
8. Write /app/output/fleet-build-compliance.json from the on-disk snapshot (all boolean success fields true only when probes pass; seal_root equals staged plan_seal).
9. Append FLEET_STAGE_ROOT/run-journal.jsonl with run_index and seal_root.

Exit non-zero if any probe fails or the API is unreachable.

Module DAG fixtures used during validation are cataloged in /app/docs/module-fixture-index.md.
