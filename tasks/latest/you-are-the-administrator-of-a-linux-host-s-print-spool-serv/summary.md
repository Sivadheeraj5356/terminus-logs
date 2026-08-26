# You are the administrator of a Linux host's **print-spool service** — the system

- **UUID:** `57793566-4577-40a6-a25e-6ccb14e3043a`
- **Slug:** `you-are-the-administrator-of-a-linux-host-s-print-spool-serv`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

You are the administrator of a Linux host's **print-spool service** — the system daemon (in the spirit of `lpd`/CUPS) that drives the machine's print devices, manages the shared spool queue of pending jobs, enforces each user's page quota, and copes with device faults. Build `spoold`, the operator control tool that replays the service's operations journal and reports the resulting service state.

The complete normative rules are in `/app/docs/spec.md` — read it carefully. Several administrative rules (quota accounting, device pause/resume, fair-share dispatch, fault handling, priority preemption) are stated deliberately and differ from a conventional priority print queue; the graded answer follows the stated rule, not the intuitive default.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
