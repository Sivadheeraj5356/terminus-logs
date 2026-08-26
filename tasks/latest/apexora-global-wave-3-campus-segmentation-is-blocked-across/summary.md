# Apexora Global Wave 3 campus segmentation is blocked across ninety-six devices u

- **UUID:** `a5317367-9c2d-4fa2-aa05-dee9bab3e7ab`
- **Slug:** `apexora-global-wave-3-campus-segmentation-is-blocked-across`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

Apexora Global Wave 3 campus segmentation is blocked across ninety-six devices under `/app/environment`. Inventory and identity still carry legacy VLAN IDs and deprecated VRF aliases, trunks and gateways violate selective policy, ACL names remain flat-network era, and deployment manifests still wire deprecated validation hooks with incomplete rollback indexing — several `/app/environment/scripts/run-netsegctl.sh` stages fail on the current tree.

Repair declarative configuration under `/app/environment` only. Treat the rollout as one dependency graph.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
