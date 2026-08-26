# acl

Offline ACL policy evaluator for the network team. Reads an ordered firewall
ruleset and a batch of observed flows. Two subcommands: `evaluate` decides allow
or deny per flow (by priority, first terminal match, default deny), records the
log rules crossed, and prints a summary; `lint` audits the ruleset and prints
the malformed, shadowed, redundant, and dead rules with a per-reason tally and a
reachability summary. See `docs/` for the ruleset format, the CIDR math, the
evaluation rules, and the exact output schema.

    make build
    ./bin/acl evaluate --rules testdata/rules_main.json --flows testdata/flows_main.ndjson
    ./bin/acl lint --rules testdata/rules_main.json --flows testdata/flows_main.ndjson

Layout:

- `cmd/acl` - the command line entry point.
- `internal/cidr` - dotted-quad parsing, canonicalization, and integer CIDR containment.
- `internal/ruleset` - loads and validates the ordered ruleset.
- `internal/eval` - priority ordering, first-terminal-match evaluation, and rule analysis.
- `internal/report` - assembles the evaluate and lint JSON reports.
- `configs/ruleset.json` - the default ruleset.
- `testdata/` - sample rulesets and flow batches.

The `--rules` flag defaults to `configs/ruleset.json` but can point anywhere.

Run `go test ./...` for the unit tests.
