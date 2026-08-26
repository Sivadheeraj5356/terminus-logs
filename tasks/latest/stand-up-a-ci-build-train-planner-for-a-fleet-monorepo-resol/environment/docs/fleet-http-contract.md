# Fleet HTTP contract

LISTEN_ADDR selects the bind address (default 0.0.0.0:8080). Verifiers may use an ephemeral loopback port. Clients must honor the active base URL and may set API_BASE for /app/scripts/emit-fleet-build-audit.sh.

## GET /health

Returns {"instance_id":"<id>","status":"ok"} where instance_id mirrors FLEETD_INSTANCE_ID (default default).

## GET /openapi.json

OpenAPI 3.1 document listing routes below.

## POST /v1/build-plan

Request: {}

Response 200: {"modules":["auth-core","billing-api","ingest-worker","notify-hub","gateway"]}

Errors:
- 400 cycle_detected when the dependency graph contains a cycle
- 400 manifest_error when a manifest references an unknown dependency ID
- 403 module_not_allowed when registry approval is required and a module is missing or pending
- 403 version_not_allowed when any module version is below the policy floor

## POST /v1/build-attest

Request: {}

Runs the same policy and graph resolution as /v1/build-plan, then binds a plan seal to the active policy fleet_release_pin.

Response 200 keys (alphabetical): modules, plan_digest, plan_seal, release_pin.

```
plan_digest = SHA256(concat(UTF-8(module_id) || 0x0a for each module in plan order))

plan_seal = SHA256(
    0x46
    || plan_digest_raw_32_bytes
    || UTF-8(fleet_release_pin)
    || pack_u32_be(module_count)
)
```

Do not omit the 0x46 domain byte. Do not hash alphabetically sorted module IDs for plan_digest. Errors mirror /v1/build-plan.

## GET /debug/policy

When debug_endpoints_enabled = false, return 404 with {"error":"not_found"}.

When enabled, return current policy fields as JSON.
