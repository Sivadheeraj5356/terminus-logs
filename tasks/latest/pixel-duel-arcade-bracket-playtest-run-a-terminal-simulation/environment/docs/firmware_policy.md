# Firmware patch drift policy

Referee poll snapshots carry `fw_q7_a` and `fw_q7_b` semver strings for the red and blue cabinets. Policy limits live in `/app/config/firmware_policy.json` under `max_patch_drift`.

The baseline loopback referee on port 7088 reports `fw_q7_a` as `1.4.2` and `fw_q7_b` as `1.4.1` in its cabinet metadata. Alternate verifier fixtures may change the policy limit without changing those poll strings.

## Patch drift calculation

Parse each firmware string as `major.minor.patch` (three dot-separated integers). When major and minor match across both cabinets, `patch_drift` is the absolute difference between patch components. When major or minor differ, set `patch_drift` to 100 to signal incompatible families.

## Policy excess

`policy_limit` copies `max_patch_drift` from config. `policy_excess` is zero when `patch_drift` is at or below the limit; otherwise it reports `patch_drift - policy_limit`.

## Firmware audit digest

Build a compact JSON object with sorted keys:

1. `fw_q7_a` — string from referee poll.
2. `fw_q7_b` — string from referee poll.
3. `patch_drift` — integer drift computed above.
4. `policy_excess` — integer excess computed above.

SHA-256 the UTF-8 bytes; lowercase hex becomes `fw_audit_digest`.
