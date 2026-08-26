# Fleet policy schema

| TOML key | Go struct field | Secure value |
|----------|-----------------|--------------|
| require_registry_approval | RequireRegistryApproval | true |
| debug_endpoints_enabled | DebugEndpointsEnabled | false |
| min_module_versions | MinModuleVersions | billing-api:2.0.0,ingest-worker:1.1.0 |
| fleet_release_pin | FleetReleasePin | line 1 of /app/fixtures/fleet-release.pin |

Parse booleans with case-insensitive true/false. Parse min_module_versions as comma-separated module_id:version pairs.

## Exact on-disk formatting

Rewrite the policy file using unquoted TOML values exactly as in the secure example below. Do not wrap booleans or pin strings in double quotes. Do not quote the min_module_versions value.

```
require_registry_approval = true
debug_endpoints_enabled = false
min_module_versions = billing-api:2.0.0,ingest-worker:1.1.0
fleet_release_pin = fleet-2025.11.4
```
