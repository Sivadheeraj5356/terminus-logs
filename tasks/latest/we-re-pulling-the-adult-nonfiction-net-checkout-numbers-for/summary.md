# We're pulling the adult-nonfiction net-checkout numbers for the fiscal-year-2024

- **UUID:** `ff25c80b-a675-4f9b-a4fa-01582c74f997`
- **Slug:** `we-re-pulling-the-adult-nonfiction-net-checkout-numbers-for`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

We're pulling the adult-nonfiction net-checkout numbers for the fiscal-year-2024 board report and need them broken down by branch. The consortium's operational data lake is at /app/data: the per-event circulation log, the item catalog, branches, patrons, holds, fines, and a lot of other operational exports.

Some of these describe circulation in more than one way or are summaries, so part of the work is figuring out which exports actually answer the question and reconciling them into one consistent figure. /app/docs/codebook.md is the data dictionary and /app/docs/question.md lists the exact output fields.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
