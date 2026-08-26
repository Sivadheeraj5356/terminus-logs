# SegmentFirst documentation index

Pipeline export shapes, field requirements, and stage gates are defined under
`schemas/pipeline/` (`exports.yaml`, `stage_gates.yaml`). Regenerate artifacts
through `scripts/run-netsegctl.sh`.

The immutable inventory, validation-scope, VLAN-range, and cumulative
configuration-authority rules are documented in `docs/OPERATIONS.md`, including
the binding transitive dependency spine:

```text
canonical VLANs
  → resolved VRFs (policy ∩ regional overrides)
  → allowed ACLs
  → rendered bundles (ACL + trunk/interface policy)
  → deployment waves
  → rollback manifests
  → evidence (fan-in)
```

Durable snapshot, bundle, and hook requirements are documented in
`docs/ROLLBACK.md`.

Assembly authority and active policy section IDs live in
`configs/assembly/source_precedence.yaml`. Wave 3 validation scope is the
static 48-host list in `inventory/wave3_validation_scope.yaml`.

Verifier computations reproduce the formulas in `docs/OPERATIONS.md`; there are
no hidden constants for VLAN range, trunk link count, regional order, ACL
allow-lists, or the trunk violations-seed schema
(`apexora-trunk-violations-1` with empty `violations`).
