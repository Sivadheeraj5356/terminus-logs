# Orchid build gate

Policy gate for the Orchid monorepo build ledger. Every dependency that enters
a build is recorded in `/app/ledger/dependency_ledger.csv`; this repo scores
each row and decides whether the build may proceed with it.

## Layout

- `/app/policy/` — the OPA Rego bundle that produces the decisions report.
- `/app/ledger/` — the current ledger snapshot, quarantine registry, and
  generation metadata.
- `/app/models/` — the pinned model registry snapshot referenced by the ledger.
- `/app/docs/` — data contracts, plus the maintainer handbook under
  `/app/docs/handbook/` (the governing document for every gate rule).
- `/app/bin/` — audit tooling.
## Usage

```
bash /app/bin/ledger-audit   # hash artifacts, build input, evaluate, write report
bash /app/bin/qa-check       # audit + validate output schema, print row-count summary
```

The audit writes `/app/out/hash_report.json`, `/app/out/policy_input.json`, and
`/app/out/decisions.json`. The policy can also be evaluated directly:

```
opa eval -d /app/policy -i /app/out/policy_input.json 'data.orchid.ledger.report'
```
