# Fleet build compliance schema

All fields required. Boolean success fields must be true when the build-train driver completes.

| Field | Type |
|-------|------|
| policy_applied | boolean |
| openapi_valid | boolean |
| release_pin_valid | boolean |
| debug_endpoint_blocked | boolean |
| build_plan_valid | boolean |
| build_attest_valid | boolean |
| approved_module_count | integer |
| policy_digest | string (lowercase SHA-256 hex of rewritten policy file) |
| plan_digest | string (lowercase hex from staged probe snapshot) |
| seal_root | string (lowercase hex; equals staged plan_seal) |

Write /app/output/fleet-build-compliance.json after the probe snapshot at /app/var/fleet-stage/build-train-probe.json is on disk. Boolean fields in the compliance report must match the probe snapshot object values. plan_digest and seal_root must be copied from the on-disk snapshot (do not re-attest during export).
