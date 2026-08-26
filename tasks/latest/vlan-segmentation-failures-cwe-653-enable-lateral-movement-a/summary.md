# VLAN segmentation failures (CWE-653) enable lateral movement across network secu

- **UUID:** `fd3ace50-acb1-4cef-8d85-4a5b73dc7d98`
- **Slug:** `vlan-segmentation-failures-cwe-653-enable-lateral-movement-a`
- **Category:** security
- **Difficulty:** hard

## Summary

VLAN segmentation failures (CWE-653) enable lateral movement across network security zones. The enforcement engine at `/app/bin/vlan-segmentation-enforce` processes 8 flows across 4 trunk ports from `/app/evidence/` and writes results to `/app/output/enforcement_result.json`.

The output JSON contains `analysis_metadata`, `summary`, `violations`, `trunk_configuration_findings`, `native_vlan_analysis`, and `violation_breakdown`. The engine must detect four violation categories on cross-VLAN flows (same-VLAN flows produce no violations).

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
