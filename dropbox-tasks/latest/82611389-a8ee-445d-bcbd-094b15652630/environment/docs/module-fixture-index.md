# Module fixture index

All manifests are CSV with columns module_id,version,depends_on. The active file is selected by the MANIFEST_PATH environment variable (default /app/data/module-manifest.csv).

## /app/data/module-manifest.csv (default acyclic graph)

Production build graph. With registry approval disabled, POST /v1/build-plan must return:

auth-core → billing-api → ingest-worker → notify-hub → gateway

## /app/data/cycle-manifest.csv (cycle detection)

Contains a three-node cycle (alpha → beta → gamma → alpha). Expected error: HTTP 400 with error cycle_detected.

## /app/data/unapproved-manifest.csv (registry enforcement)

Contains legacy-bridge at version 0.9.0 seeded as pending. When require_registry_approval = true, expect HTTP 403 with error module_not_allowed.

## /app/data/low-version-manifest.csv (semver floor enforcement)

Same shape as default, but billing-api is 1.9.0 below secure floor 2.0.0. Expect HTTP 403 with error version_not_allowed.

## /app/data/high-version-manifest.csv (numeric semver)

Same shape as default, but billing-api is 10.0.0. Numeric comparison must accept floor 2.0.0 (lexicographic comparison would fail).

## /app/data/tiebreak-manifest.csv (stable Kahn tail append)

Initial ready set is a-unit and c-unit. Unlocking a-unit yields b-unit; unlocking c-unit yields d-unit. Correct order is a-unit → c-unit → b-unit → d-unit. Fully re-sorting the queue after each unlock yields a different order and must fail.

## /app/data/diamond-manifest.csv (diamond dependency)

root-unit unlocks left-unit and right-unit; both feed merge-unit. Expected order: root-unit → left-unit → right-unit → merge-unit.

## /app/data/missing-dep-manifest.csv (missing dependency)

billing-api depends on missing-unit which is absent from the manifest. Expected error: HTTP 400 with error manifest_error (not cycle_detected).
