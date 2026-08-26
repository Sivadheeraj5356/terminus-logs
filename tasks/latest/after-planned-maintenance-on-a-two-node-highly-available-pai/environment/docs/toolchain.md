# Toolchain

Sources live under `/app/environment`. Rebuild and install the operator CLI
after changing the cluster control stack:

```bash
make -C /app/environment install
```

The installed binary is `/usr/local/bin/vivostep`.

## Commands

| command | role |
|---------|------|
| `vivostep run --scenario wp-maint` | run the maintenance return scenario |
| `vivostep run --scenario wp-maint --cold` | cold-start path for the same scenario family |
| `vivostep reopen` | simulate a process reopen boundary |
| `vivostep examine --surface dual` | print both authority measurements |
| `vivostep emit -o /app/output/wp_report.json` | write the cycle report |

Optional schedule seed for interleave variants:

```bash
VIVO_SCHED_SEED=2 vivostep run --scenario wp-maint
```

Runtime state is under `/app/data`. Field semantics and digest rules are in
`docs/contract.md`.
