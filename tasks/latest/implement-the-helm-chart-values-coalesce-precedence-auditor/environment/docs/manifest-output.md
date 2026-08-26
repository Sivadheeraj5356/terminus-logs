# Manifest output

## Top-level JSON

| Field | Type | Description |
|-------|------|-------------|
| `active_charts` | string[] | Manifest chart ids included after condition filtering, sorted. |
| `values` | object | Map of chart id → coalesced values object (sorted keys). |
| `precedence_trail` | array | Sorted trail rows per coalesce-contract.md. |
| `manifest_hash` | string | `sha256:` + lowercase hex of canonical JSON payload. |

## manifest_hash

Compute from the manifest object **excluding** `manifest_hash`. Canonical JSON:

- Object keys sorted lexicographically at every level.
- No insignificant whitespace.
- Trail array already sorted before hashing.

## Snapshot

Successful resolve also writes `/app/state/helmvals-resolve-snapshot.json` with identical bytes to `--out`.
