# Task Proposal Pipeline — commitment-carrydown-chargeback-debug

Use the fields below in the Snorkel **Task Proposal Pipeline** before building or submitting. Click **Check Feedback** only; do **not** submit the proposal itself.

## Task Idea Summary

Finance rejected the March commitment chargeback binary at `/app/bin/commitment-chargeback`. The agent repairs a mostly-correct Go `carrydown_engine` with interacting bugs (rate scope/file-order ties, half-open windows, stateful pledge carrydown, credit-before-commitment, net-weighted largest-remainder pools, ledger-order digest) under rules in `/app/billing_contracts/SCHEMA.md`, then writes only `/app/output/ledger.json` from locked `/app/pledge_inputs`. Domain focus is commitment pledge carrydown chargeback—not minimum-spend trueup, ingest backfill, or cloud metering settlement.

## Idea Category

**data-processing** (subcategory: **tool_specific**)

## Associated Skills

- Go multi-file billing engine repair (`carrydown_engine`)
- Half-open rate windows and scope precedence (tenant over region over global, first file match)
- Per-service commitment carrydown with running pledge unit decrement
- Credit-before-commitment precedence (read from config each run) and net-weighted largest-remainder pools
- Deterministic ledger JSON and SHA-256 pipe-row digest from SCHEMA.md
- Embed usage shard filenames as Go string literals; offline stdlib-only `go build` with absolute `/app` path constraints

## Task Tags

- chargeback
- commitment-carrydown
- billing-repair
- go
- determinism
- data-processing

## Checklist Before Building / Submitting

- [ ] Ran **Check Feedback** in Task Proposal Pipeline
- [ ] Tags and category match `task.toml` and this proposal
- [ ] Oracle passes; agent difficulty recalibrated on **GPT-5.5** and **Opus 4.8**
- [ ] `[environment] allow_internet = false` and verifier deps baked into Dockerfile
