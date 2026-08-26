# Fleet hosts in US/Eastern run a nightly consolidation cron that keeps durable to

- **UUID:** `e588172b-0e0e-4941-a274-ffdd969e443b`
- **Slug:** `fleet-hosts-in-us-eastern-run-a-nightly-consolidation-cron-t`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

Fleet hosts in US/Eastern run a nightly consolidation cron that keeps durable totals under /var/lib/acct and rebuilds an offline daylight-saving schedule history into /app/output/schedule_ledger.json. Disk, load, and cron.service probes stay green, but after local clock transitions the recorded schedule no longer matches what operators expect.

Window indexes live under /app/data/windows/{backward,forward,resume}/window.conf (passed to step_tool as --env), fragment snapshots live under /app/data/traces, and the host-side rebuild helpers and policy sources live under /app/environment (including shared cadence settings in m5s/cadence_policy.conf). Around the autumn fall-back weekend, one calendar day sometimes shows two completed runs with the same YYYYMMDD day stamp but different wall-time offsets inside the repeated local hour, and stored totals run high.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
