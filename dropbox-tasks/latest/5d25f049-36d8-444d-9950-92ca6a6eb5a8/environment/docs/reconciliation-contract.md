# Reconciliation contract

Managed objects carry durable annotations with `logical_id`, `generation`, `phase`, `tenant`, and optional `counter_lineage`.

Recovery reconciles desired intent, committed manifest, pending manifest (when present), and observed backend state.

## Pending phases

Public failpoints may leave pending manifest phases:

- `after-stage-sets`
- `after-stage-chains`
- `after-publish-references`
- `after-manifest-publish`

A pending generation whose backend objects are complete for the desired intent may be adopted. Incomplete pending managed objects are removed or rebuilt. Foreign objects are never deleted because they share a visible name with a managed object.

Ownership is proven by manifest entries and annotations, not visible names alone.

## Counter lineage

Packet counters follow logical rule identity and compatible semantic revision through `counter_lineage`. Counters do not follow transient backend handles.

## Legacy manifests

Schema version 1 manifests upgrade to version 2 while preserving `counter_lineage` on every entry.

## Validation atomicity

`apply` and `recover` must validate the complete effective configuration before mutating backend, manifest, counters, or audit state. A rejected configuration leaves all durable state unchanged.

## Canonical digests

Effective intent digests are sha256 hashes over sorted set and rule payloads. State file fingerprints use sha256 over raw file bytes.
