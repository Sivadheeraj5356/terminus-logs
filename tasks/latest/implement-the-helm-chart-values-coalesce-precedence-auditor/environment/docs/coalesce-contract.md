# Coalesce contract

## YAML subset

Indentation is two spaces per level. Maps use `key: value`. Lists use `- item` with one scalar per line. Scalars may be booleans (`true`/`false`), integers, floats, bare tokens, or double-quoted strings.

## Merge semantics

`Merge(dst, src)` deep-merges maps: when both sides hold maps at the same key, recurse. Otherwise `src` replaces `dst` at that key (scalars and lists are replaced entirely; lists are never appended).

## Layer order per chart

For the root chart:

1. `defaults` — root `values.yaml`.
2. Each `--values` file in CLI order (full document merged at root scope).
3. Each `--set` pair in CLI order (see cli-contract.md).

For each active subchart:

1. `defaults` — subchart `values.yaml`.
2. `parent` — subtree from the parent release values under the subchart values key (alias or name).
3. Each `--values` file in CLI order (merge the subtree under the subchart values key when present).
4. Each `--set` pair whose chart prefix matches the subchart manifest id.

`--set` keys may be prefixed with `<chartId>.` to target a subchart; unprefixed keys target the root chart.

## Global propagation

After every layer in steps 1–3 that contains a `global` map, deep-merge that `global` map into the `global` key of **every** active chart's coalesced values. Global merges use the same map semantics. Later layers win on scalar conflicts inside `global`.

## Precedence trail

Each leaf assignment records:

```json
{"chart": "id", "path": "dot.path", "value": <json>, "layer": "defaults|parent|values|set", "ordinal": <int>}
```

`ordinal` increases monotonically across the full resolve in layer application order (root defaults first). Within a single layer application, leaf paths process in lexicographic order. `path` never includes the chart id prefix. Trail rows sort by `(chart, path, ordinal)` before export.

## Determinism

`active_charts` sorts lexicographically. `values` object keys sort lexicographically. Map keys inside exported values sort lexicographically at every nesting level in JSON output.
