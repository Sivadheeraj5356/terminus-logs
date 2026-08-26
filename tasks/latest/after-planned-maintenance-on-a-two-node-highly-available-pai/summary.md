# After planned maintenance on a two-node highly available pair, automated failbac

- **UUID:** `f7c2b75b-dc84-4210-b261-1db82d0eac44`
- **Slug:** `after-planned-maintenance-on-a-two-node-highly-available-pai`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

After planned maintenance on a two-node highly available pair, automated failback brings the floating service endpoint back on the preferred node. Health probes on the VIP in `/app/environment/configs/pair.toml` stay green, yet downstream clients report intermittent reachability failures for several minutes when the maintenance window closes.

Operator exports from maintenance returns list `endpoint_attach` ahead of `neighbor_replay` in `gate_timings`. A supervisor reload (`vivostep reopen`) leaves `vivostep examine --surface dual` with mismatched forwarding and journal epochs on the next maintenance return.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
