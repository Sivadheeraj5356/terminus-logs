# You administer an offline networkd bonding ARP-monitor reconcile deployment unde

- **UUID:** `2f3ef62d-32d5-4dad-ae68-2a9c4c4c8c1a`
- **Slug:** `you-administer-an-offline-networkd-bonding-arp-monitor-recon`
- **Category:** system-administration
- **Difficulty:** medium

## Summary

You administer an offline networkd bonding ARP-monitor reconcile deployment under `/app/environment`. After a MAC failover drill the deployment no longer meets its documented operational policy: egress still steers toward a downed member, ARP monitor pressure never fully settles, a staging-only ghost peer keeps entering the working set, back-to-back drills stop lining up with the durable lineage ledger, and the local status probe reports convergence that the sealed artifacts do not support.

The first drill after the incident often looks fine; it is the second and later drills, replays, and recover runs that drift. Build and run commands are in `/app/environment/docs/run_cmds.txt`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
