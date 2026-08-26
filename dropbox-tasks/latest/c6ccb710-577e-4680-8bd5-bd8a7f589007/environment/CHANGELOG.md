# Changelog

## 1.4.2
- Packaging gate alignment for flood-tide window.
- packaging_build contract recorded in the normative pack ledger (stream profile
  define, compat-tree exclusion, restored Scan/Classify/Emit under src, project-local
  override rule, version alignment).

## 1.4.0
- GHC 9.0 migration: stream handling moved to the gate-v2 profile named in the
  normative ledger. Tide-era code paths retired; compat trees kept for the
  8.10 audit trail only and must not ship.

## 1.3.0
- Initial drydock console scaffold.
