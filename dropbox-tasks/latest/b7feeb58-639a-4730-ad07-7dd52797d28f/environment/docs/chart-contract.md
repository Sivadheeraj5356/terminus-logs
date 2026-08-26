# Chart contract

## Layout

A chart directory contains:

- `Chart.yaml` — chart metadata and optional `dependencies` list.
- `values.yaml` — default values for the chart (may be absent; treated as empty).
- `charts/<dependency-name>/` — vendored subchart directories keyed by dependency `name` (not alias).

## Chart.yaml

Required keys: `name`, `version`. Optional `dependencies` array. Each dependency object has:

| Field | Required | Meaning |
|-------|----------|---------|
| `name` | yes | Subchart directory name under `charts/`. |
| `version` | yes | Declared version string (opaque to helmvals). |
| `alias` | no | Values key and manifest chart id when present; otherwise `name` is used. |
| `condition` | no | Dot-path evaluated against the parent chart release values (see condition-contract.md). |

## Values key

When a parent passes values to a subchart, the subtree key is `alias` when set, otherwise `name`.

## Manifest chart id

`active_charts` and `values` top-level keys use the manifest chart id: root chart `name`, subcharts use `alias` or `name`.

## Parsing

`Chart.yaml` and `values.yaml` use the YAML subset defined in coalesce-contract.md (maps, scalars, booleans, integers, floats, quoted strings).
