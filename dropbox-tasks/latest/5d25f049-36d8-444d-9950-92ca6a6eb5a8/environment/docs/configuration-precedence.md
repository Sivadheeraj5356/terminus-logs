# Configuration precedence

Effective policy is assembled from:

1. `/app/config/base.toml`
2. Drop-ins under `/app/config/conf.d/*.toml`
3. Runtime overrides at `<state-dir>/runtime-overrides.json`

Drop-ins merge in ascending order of normalized absolute path within each priority band. When two drop-ins set the same rule or set id, the drop-in with the lower `priority` number wins. When priorities tie, the later path in ascending normalized path order wins. TOML files use `=` between keys and values.

Runtime overrides may change only the `action` field of an existing rule id. An override containing `tenant` or `ownership_scope` is invalid and must be rejected with an error and a non-zero command exit before durable state is changed. Silently ignoring or discarding a protected field is not permitted. Validation, apply, and recovery paths that load runtime overrides must reject such overrides before mutating the backend, ownership manifest, or audit state.

## Effective configuration inspection

`nxctl validate` rejects unknown set references and duplicate ordered rule ids within a chain.
