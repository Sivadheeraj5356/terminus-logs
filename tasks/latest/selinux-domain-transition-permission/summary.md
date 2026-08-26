# # SELinux Domain Transition Permission

- **UUID:** `4c297dcc-2133-4ba9-97bd-82e19c299258`
- **Slug:** `selinux-domain-transition-permission`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

The domain-transition lab replays three case batches through a hop-check CLI. After a clean rebuild and pipeline run, the emitted security report shows accepted transitions where policy traps should deny, disagreement between configured, sampled, and live grant masks on the same row, and incorrect accept tags when an identical role label appears under a different pivot key in a later batch.

Replay batches listed in `/app/docs/d8_run_notes.md`, then run `/app/tools/h2_runner` and `/app/tools/q1_emit`. The hop runner writes `/app/var/d8_raw.jsonl` and `/app/var/d8_pivot.jnl`; the emitter writes `/app/output/d8_observations.json` and `/app/var/d8_stamp.txt`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
