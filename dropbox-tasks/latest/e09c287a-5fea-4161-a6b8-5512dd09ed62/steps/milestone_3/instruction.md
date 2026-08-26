# Referral portfolio assignment

For the final step, add the assignment command to the Go CLI in `/workspace`:

`go run /workspace/cmd/claimtower assign --index-in <index.json> --capacity <capacity.tsv> --plan <plan.json> --assignments-out <tsv> --summary-out <json> --issues-out <tsv>`

This command consumes the milestone 2 signal index, the team capacity roster, and a strict assignment-plan JSON. It must choose claims, review days, and teams as one deterministic portfolio optimization rather than greedily assigning claims one at a time. The complete visible schema, validation rules, relationship semantics, objective order, and output fields are in `/workspace/docs/claimtower-contract.md` under Milestone 3.

The capacity TSV keeps the fixed seven-column schema `team`, `products`, `counties`, `day1`, `day2`, `risk_ceiling`, and `active`. Malformed headers and rows remain recoverable. After a malformed header, continue parsing later rows positionally against the fixed schema so valid teams still load and later bad rows still emit `invalid_capacity` issues.

The assignment-plan JSON is strict and fatal when malformed. It defines a global score budget, per-team/day score budgets, primary-signal skills, claim day windows, same-day blocks, dependencies, precedence, same-team groups, different-team pairs, and bundle bonuses. Every valid capacity team must have a score-limit entry and a nonempty skill list. Unknown fields, unknown claim or team references, invalid days, invalid pairs or groups, negative limits, and missing required top-level fields must fail before any requested output is created or replaced.

A team is statically eligible for a claim only when it is active, product and county match, the claim score does not exceed the team risk ceiling, and the team can handle the claim's primary signal. The primary signal is the first signal in the milestone 2 index. Claims with no statically eligible team use `hold_no_team`; claims with a statically eligible team that are omitted because of budgets, day windows, capacities, or portfolio relationships use `backlog_capacity`.

Among all feasible schedules, maximize the documented `plan_value`, then maximize assigned claim count, then minimize assigned raw score, then choose the lexicographically smallest schedule key. The contract defines exactly how dependencies, precedence, continuity, separation, bundle bonuses, day limits, and the schedule key work.

Keep the assignment TSV in lane-processing order. The summary JSON must include portfolio value, bonus value, raw score used, day summaries, and team count/score usage. Preserve deterministic JSON/TSV formatting, parent-directory creation, issue ordering, final newlines, and the standard-library-only, offline execution constraints.
