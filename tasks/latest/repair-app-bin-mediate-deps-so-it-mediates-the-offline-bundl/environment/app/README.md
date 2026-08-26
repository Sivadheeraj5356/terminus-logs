# Indigo Palisade Mediator

Offline dependency mediation and classpath audit for Maven-style coordinates.

## Command

```bash
/app/bin/mediate-deps \
  --data-dir /app/data \
  --out-json /app/out/audit.json \
  --out-classpath /app/out/classpath.csv \
  --out-mediation /app/out/mediation.csv \
  --out-findings /app/out/findings.csv
```

Read `/app/mediation-policy.md` for mediation rules and `/app/schemas` for output formats.

The default bundle in `data/` is useful for end-to-end validation, but some policy edge cases are easier to reproduce with the focused bundles in `examples/`. In particular, `examples/nearest-tie/` and `examples/topo-order/` isolate equal-depth mediation conflicts and dependency-ordering behavior. Those example bundles include only the inputs they need; optional policy files are documented in `schemas/inputs.schema.md`.

`examples/topo-order/` mirrors the relocation rows from `data/` and is useful for debugging classpath ordering, but you must still validate `/app/data` afterward. In the full bundle, `org.alpha:gateway` depends on relocated core coordinates, so `org.alpha:core` must appear before `org.alpha:gateway` in `classpath.csv`.

## Layout

- `data/` — input bundle (roots, repository, BOM, policy CSVs)
- `examples/` — focused scenarios for local debugging
- `fixtures/` — malformed inputs for fatal validation
- `src/indigo/` — Clojure mediation engine
- `schemas/` — output contracts
