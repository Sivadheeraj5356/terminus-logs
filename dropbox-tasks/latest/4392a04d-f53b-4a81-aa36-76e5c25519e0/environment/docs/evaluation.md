# Evaluation and rule analysis

## Flows

The flows file is NDJSON: one JSON object per line, blank lines ignored. A flow
is:

    {"src":"10.5.5.5","dst":"192.168.1.10","port":22,"protocol":"tcp","direction":"inbound"}

`src` and `dst` are addresses, `port` is the destination port, `protocol` is
`tcp`/`udp`/`icmp`, `direction` is `inbound`/`outbound`. Flow input is trusted: a
line that will not parse as JSON is skipped and does not appear in the report.
Decisions come out in the same order as the input flows.

## Evaluation order

Rules are NOT consulted in file order. The loaded rules are ordered by
`priority` descending; ties are broken by ascending file index. That derived
order is what "first match" and "an earlier rule" mean everywhere below, in both
`evaluate` and `lint`. A low-index rule with a low priority can be consulted
after a high-index rule with a high priority.

## When a rule matches a flow

A rule matches a flow when all five hold:

- the flow `src` is inside the rule's canonical `src` block (see `cidr-math.md`),
- the flow `dst` is inside the rule's canonical `dst` block,
- the flow `port` is within the rule's inclusive `[port_min, port_max]` range,
- the rule `protocol` is `any`, or equals the flow `protocol`,
- the rule `direction` is `any`, or equals the flow `direction`.

## First terminal match, log rules, default deny

Walk the rules in evaluation order. For each rule that matches the flow:

- if its `action` is `log`, record the rule's id and KEEP GOING - a log rule
  never decides a flow,
- if its `action` is `allow` or `deny`, that is the decision: its action becomes
  the decision string and its id becomes the matched id. STOP; do not consult any
  later rule.

If no terminal rule matches, the flow is denied by default: the decision is
`deny` and the matched id is the sentinel string `default-deny` (not null, not an
empty string, and never a real rule id). Any log rules crossed before falling
through are still recorded, so a default-denied flow can carry a non-empty log
list. A flow whose `src` or `dst` is not a parseable address is denied by default
with no rules consulted and an empty log list.

The log ids for a flow are listed in the order the log rules were crossed, that
is, in evaluation order.

## Which rules fired

A rule "fired" for a batch when it matched at least one flow: a terminal rule
that was the deciding match, or a log rule that was crossed. A terminal rule that
sat behind an earlier terminal match for every flow never fired. The fired set is
what the reachability analysis below consumes.

## Analysis: shadowed, redundant, unreachable

The analysis classifies each LOADED rule (dropped rules are not classified) into
exactly one bucket, in this precedence:

1. `shadowed` - some EARLIER rule in evaluation order is a terminal rule (`allow`
   or `deny`, never `log`) that covers this rule on every dimension, so this rule
   can never be the first terminal match. "Covers" means: the earlier rule's
   `src` block covers this rule's `src` block AND its `dst` covers this `dst`
   (see `cidr-math.md`) AND its port range contains this range
   (`earlier.port_min <= this.port_min` and `earlier.port_max >= this.port_max`)
   AND its protocol is `any` or equal AND its direction is `any` or equal. The
   detail is the file index of the first such covering rule, as a string. This is
   structural: it does not depend on the flows.
2. `redundant` - not shadowed, but some earlier rule in evaluation order matches
   exactly the same packets with the same action (identical canonical `src` and
   `dst`, identical port range, protocol, direction, and action). The detail is
   the file index of the first such earlier rule, as a string. Also structural.
3. `unreachable` - loaded, not shadowed, not redundant, and did not fire for this
   batch. The detail is the empty string. This depends on the flows: with no
   `--flows`, nothing fired, so every live rule that is neither shadowed nor
   redundant is unreachable.
4. otherwise the rule is `reachable` and is not listed in any finding array; it
   is only counted in the summary.

Because a log rule is non-terminal, it never shadows a later rule, and two
identical log rules make the second `redundant` (it logs nothing new) even though
both fire.

The shadow test in step 1 applies to every loaded rule, log rules included: a
log rule is `shadowed` when an earlier terminal rule covers it on every
dimension, because that earlier terminal match ends evaluation before the log
rule is ever consulted, so the log rule can never fire. A log rule that is both
covered by an earlier terminal rule and identical to an earlier log rule is
`shadowed`, not `redundant`, by the precedence above: so among two identical log
rules the second is `redundant` only when no earlier terminal rule covers it,
and `shadowed` otherwise.

## Consistency with evaluate

The two subcommands share the same ordering, canonicalization, and match rules,
so they must agree: a rule that `lint` reports as shadowed, redundant, or
unreachable can never be the terminal `matched` id of any decision in `evaluate`
for the same ruleset and flows, and every non-sentinel `matched` id names a rule
`lint` counts as reachable.
