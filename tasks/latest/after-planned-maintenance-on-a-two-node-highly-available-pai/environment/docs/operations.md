# HA pair failback operations

This node ships a two-node highly available service pair with a floating VIP
(`service_vip` in `configs/pair.toml`). Maintenance on the standby node is
followed by automated failback to `preferred_node` when the window completes.

Failback must refresh neighbor state on the L2 publish path before the floating
endpoint is attached on the forwarding route table. Operator convergence is
tracked through the forwarding table authority and the durable event journal;
both must agree before clients can rely on reachability through the VIP.

Pair layout and probe targets live in `configs/pair.toml`. Maintenance scenarios
live under `configs/scenarios/`. Operator repro:

```bash
scripts/run_failback_check.sh
```

Typical operator workflow after a maintenance window:

```bash
vivostep run --scenario wp-maint --cold
vivostep run --scenario wp-maint
vivostep examine --surface dual
vivostep emit -o /app/output/wp_report.json
```

After a supervisor reload, use `vivostep reopen` before the next maintenance
return when stale journal generations must be dropped below the active forwarding
epoch.

Field semantics for exported reports are in `contract.md`. Convergence
coordination rules are in `coordination.md`. Rebuild steps are in `toolchain.md`.
