You are the administrator of a Linux host's **print-spool service** — the system
daemon (in the spirit of `lpd`/CUPS) that drives the machine's print devices,
manages the shared spool queue of pending jobs, enforces each user's page quota,
and copes with device faults. Build `spoold`, the operator control tool that
replays the service's operations journal and reports the resulting service state.

The complete normative rules are in `/app/docs/spec.md` — read it carefully.
Several administrative rules (quota accounting, device pause/resume, fair-share
dispatch, fault handling, priority preemption) are stated deliberately and differ
from a conventional priority print queue; the graded answer follows the stated
rule, not the intuitive default. There is exactly one correct output per input.

The scaffold is a Go module rooted at `/app`; build with
`go build -o /app/bin/spoold ./cmd/spoold`. Implement the full engine and every
command in `/app/internal/sp/sp.go`, which currently holds a stub.

Every command prints canonical JSON to stdout and is graded **byte-for-byte**;
match the spec's serialization, key ordering, `null` rendering, and trailing
newline exactly. Implement:

- `log` — the replayed journal outcomes.
- `printers` — per-printer current job and paused flag.
- `queues` — each printer's waiting spool queue.
- `jobs` — every job with its final state.
- `owners` — per-owner quota accounting.
- `trace` — printer state after the first n events.
- `verify` — structural check of the journal.
- `preemptions` — recorded preemption events.
- `aborts` — jobs aborted at the fault ceiling.
- `job` — one job's full record.

Sample inputs (no reference outputs) are under `/app/data/schedules/` and
`/app/data/examples/`; the rules in spec.md govern the hidden graded schedules.
