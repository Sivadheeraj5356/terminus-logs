# Queue Lint Specification

`queue-lint` runs six fixed-order domain integrity rules against the current
database state and reports violations for each. Rules do not depend on each
other, and every rule always runs even if an earlier rule already failed.

## Fixed Rule Order

This is the order rules are checked in and printed in. It is **not**
alphabetical, matching the fixed-order convention `escalation-audit` uses
instead of the alphabetical order `priority-stats` uses:

1. `TIER_CAPACITY`
2. `STATUS_VALID`
3. `DUPLICATE_RESOLUTION`
4. `ORPHAN_RESOLUTION`
5. `SLA_CONSISTENCY`
6. `CHAIN_SEQUENCE`

## Output Format

For each rule, print one summary line:

```
<RULE_NAME> <PASS|FAIL> violations=<N>
```

`<N>` is the count of distinct violating identifiers for that rule. If `<N>`
is greater than zero, print each violating identifier on its own line
immediately after the summary line, sorted ascending, each prefixed with a
single leading tab character:

```
	<identifier>
```

After all six rule blocks, print one final line:

```
OVERALL <PASS|FAIL>
```

`OVERALL` is `FAIL` if any of the six rules failed, and `PASS` only if all
six passed. **Exit code** is 0 when `OVERALL` is `PASS`, 1 otherwise.

## Rule Definitions

### TIER_CAPACITY

An agent violates this rule when the count of tickets with `status='open'`
and `assigned_agent_id` equal to that agent's `agent_id` exceeds that
agent's tier capacity (same capacities as `workload-balance`: L1=5, L2=15,
L3=30). Violating identifier: `agent_id`.

### STATUS_VALID

A ticket violates this rule when its `status` column is not one of `open`
or `resolved`. Unlike `tier` and `priority`, there is no database-level
CHECK constraint on `status`, so this is the only rule that catches a
directly tampered or corrupted status value. Violating identifier:
`ticket_id`.

### DUPLICATE_RESOLUTION

A `ticket_id` violates this rule when it appears more than once in the
`resolutions` table. Violating identifier: `ticket_id`, printed once per
duplicated `ticket_id` regardless of how many extra rows exist for it.

### ORPHAN_RESOLUTION

A row in `resolutions` violates this rule when its `ticket_id` does not
match any row in `tickets`, or matches a ticket whose `status` is not
`resolved`. Violating identifier: `ticket_id`.

### SLA_CONSISTENCY

A row in `resolutions` violates this rule when its stored `sla_met` value
does not match the value independently recomputed from that row's own
`resolution_minutes` against its ticket's priority SLA threshold
(critical=60, high=240, medium=1440, low=4320, using the same `<=`
inclusive rule `resolve-ticket` uses). This rule recomputes from
`resolution_minutes` and the ticket's `priority` rather than trusting the
stored `sla_met` value at face value — the same "recompute rather than
trust" principle `chain-verify` applies to the audit chain. Violating
identifier: `ticket_id`.

### CHAIN_SEQUENCE

Read all `chain_id` values from `resolution_chain` ordered ascending.
Walking that ordered list with a 1-indexed running counter starting at 1, a
row violates this rule when its `chain_id` does not equal the current
counter value at that position. This catches any deleted or non-contiguous
row anywhere in the chain, not only a deleted head entry — `chain-verify`
already catches head deletion separately via `prev_hash` linkage, but a
deletion in the middle or tail of the chain does not break that linkage the
same way and needs this separate structural check. Violating identifier:
the row's actual `chain_id`, formatted as a decimal string with no leading
zeros.

If `resolution_chain` is empty, this rule passes with `violations=0`.
