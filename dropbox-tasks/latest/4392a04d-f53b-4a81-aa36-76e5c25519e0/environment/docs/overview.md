# acl

Offline ACL policy tool the network team runs before pushing a firewall change.
You give it an ordered ruleset and a batch of observed flows. It has two
subcommands, each printing one JSON object to stdout:

- `evaluate` decides, flow by flow, whether the ruleset allows or denies each
  one, records every log rule crossed on the way, and prints a summary.
- `lint` audits the ruleset itself and prints the malformed, shadowed, redundant,
  and dead rules, plus a per-reason tally and a reachability summary.

Under the hood the work is three parts that feed each other:

1. Load and validate every rule (id, action, src/dst block, port range,
   protocol, direction, priority). Bad rules are dropped but keep their file
   index. Valid blocks are canonicalized and a snapped block is noted.
2. Order the surviving rules and evaluate each flow against them by first
   terminal match, defaulting to deny, tracking which rules fired.
3. Analyse the ordered set: which rules are shadowed by an earlier rule, which
   duplicate an earlier rule, and which never fired.

`evaluate` prints step two. `lint` folds the load-step notes from step one and
the analysis-step findings from step three into one report. The point of `lint`
is that a ruleset can evaluate cleanly and still be quietly broken: a rule
shadowed by a broader rule ahead of it, a duplicate that never adds anything, a
typo'd block that silently never applies, a live rule no traffic reaches. Both
the load-time notes and the analysis-time findings have to reach the lint
output, and the ordering that decides both is the same one `evaluate` uses.

The five format docs in this folder are the contract:

- `ruleset-format.md` - what a rule is and which rules we reject at load time.
- `cidr-math.md` - how addresses and blocks are compared and canonicalized.
- `evaluation.md` - priority ordering, first terminal match, log rules, default
  deny, and the shadowed/redundant/unreachable analysis.
- `report-schema.md` - the exact JSON each subcommand prints.

Run it like:

    acl evaluate --rules testdata/rules_main.json --flows testdata/flows_main.ndjson
    acl lint --rules testdata/rules_main.json --flows testdata/flows_main.ndjson

`--rules` defaults to `configs/ruleset.json` but can point anywhere. For `lint`,
`--flows` is optional: without it, no rule counts as reached.
