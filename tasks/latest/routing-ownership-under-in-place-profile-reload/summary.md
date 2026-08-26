# # Routing ownership under in-place profile reload

- **UUID:** `541ca227-bc27-4924-bd15-107eb21e61a9`
- **Slug:** `routing-ownership-under-in-place-profile-reload`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

`/app/bin/linkctl` is the offline link-policy control plane for topology profiles under `/app/data/topology_w3/` and grant/withdraw events in `/app/var/grant_feed.jsonl`. Operators drive cold boot, in-place profile reload, and WAL-backed state reconstruction with `bash /app/scripts/run_link_ops.sh <profile>` and `linkctl recover --root /app/var/state --out /app/output`.

Each run must leave `/app/output/effective_fib.json`, `/app/output/link_status.json`, and `/app/output/reconfigure_journal.jsonl` aligned with `/app/environment/docs/operator_contract.md`:

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
