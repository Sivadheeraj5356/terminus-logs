# We run a small group of replicas that keep an ordered, authenticated log of clie

- **UUID:** `b238a6ec-530b-4788-93d9-e02392edc2df`
- **Slug:** `we-run-a-small-group-of-replicas-that-keep-an-ordered-authen`
- **Category:** security
- **Difficulty:** hard

## Summary

We run a small group of replicas that keep an ordered, authenticated log of client operations. Every replica shares one cluster key, but the network is hostile: it drops, reorders, duplicates, and replays messages, opens and heals partitions, and injects messages no replica ever sent.

You write the replica fresh in /app/src/LogReplica.java against the Replica interface, MsgKind tags, and AuthCode helper. /app/docs/interface.md is the type, lifecycle, and timing reference, /app/docs/contract.md states the guarantees the group keeps, and bash /app/smoke.sh replays sample schedules.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
