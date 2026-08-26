# Policy contract

## Precedence (highest to lowest)

1. **Workspace overlays** — modules listed in an adjacent `go.work` `use` directive override remote/replace selections for that module path. When a workspace module wins, `source` is `workspace` and `policy_decision` is `workspace_override`.
2. **Replace directives** — request `replaces[]` entries rewrite module paths before policy lookup. A winning replace uses `source` `replace` and `policy_decision` `replace_applied`.
3. **Organization policy pins** — rows in the SQLite index for the active `policy_revision`, `goos`, and `goarch`. Pin decisions commonly use `allow` (see `policy/pins.jsonl`).
4. **Mirror defaults** — versions from the offline module mirror when no pin exists (`source` `mirror`).

## Replace total order

When multiple replace directives apply to the same `old_path`, apply them in deterministic total order:

1. Sort by `old_path` ascending.
2. For equal `old_path`, sort by `new_path` ascending.

The last applicable replace in that order wins for resolution.

### Example (replace-conflict workspace)

Request replaces for `corp.example/fork` declare `corp.example/fork-beta` then `corp.example/fork-alpha`. After sorting by `new_path`, the winner is `corp.example/fork-beta` at `v1.1.0-beta`.

### Example (workspace-override)

`corp.example/wslib` appears in `go.work`; the workspace overlay beats both the remote replace to `corp.example/wslib-remote` and organization pins (which list `v1.2.0`), keeping mirror/local `v1.0.0` with `workspace_override`.

### Example (platform-pin)

`corp.example/cgoish` is pinned to `v1.0.0` on `linux/amd64` and `v2.0.0-arm` on `linux/arm64`.

### Unauthorized modules

Paths absent from the pin allowlist and mirror (for example `corp.example/banned`) must fail with exit `23`.

## Decision identity

Decision entries must incorporate module path, selected version, `goos`, `goarch`, and active `policy_revision`.

## Index completeness

`index_meta.index_complete` may be `1` only after all pin rows for the current revision are committed atomically. Partial writes must leave `index_complete=0` or roll back.
