# Input contract

## EDN

Maps, vectors, strings, keywords, booleans, nil, integers, symbols.

## CSV

UTF-8, comma separators, required header rows, double-quote escaping.

## Coordinates

Artifact coordinates use `group:name`.

## Required files under `--data-dir`

- `roots.edn`
- `local_repo.edn`
- `bom.edn`
- `checksums.csv`

## Optional files

When omitted, the loader supplies neutral defaults:

- `relocations.csv` — header `from_coord,to_coord,reason` with zero data rows
- `license_policy.csv` — header `license,status` with zero data rows (all licenses unknown)
- `mediation_config.edn` — default policy:

```clojure
{:run-id "indigo-default"
 :scope-order [:compile :runtime :test]
 :include-scopes #{:compile :runtime}
 :optional-default false
 :checksum-mode :report
 :cycle-mode :fatal}
```

Focused bundles under `/app/examples/` may omit optional files; copy the full `/app/data` bundle when you need the production policy tables.
