# The image-rendering lab has ten diagnostic workstations that can no longer host

- **UUID:** `f197e256-a033-4e4f-ba72-a8f1d152b7a3`
- **Slug:** `the-image-rendering-lab-has-ten-diagnostic-workstations-that`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

The image-rendering lab has ten diagnostic workstations that can no longer host Valgrind or gdb sessions because a recent image refresh left them with an unsafe mix of ptrace, core-dump, group-membership, ulimit, and filesystem-permission settings. Your job is to author an Open Policy Agent Rego library under `/app/policy/` that translates each workstation's compliance state, sourced from the DuckDB inventory at `/app/inventory/workstations.duckdb` (view `v_workstation`), into an ordered remediation plan that matches the canonical decision matrix documented in `/app/postmortem/postmortem.md`.

The postmortem is long but complete; every rule, every exact action string, and the required ordering are stated there. Your library must declare `package workstation.plan` and expose `actions` at `data.workstation.plan.actions`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
