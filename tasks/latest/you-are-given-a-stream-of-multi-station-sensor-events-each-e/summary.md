# You are given a stream of multi-station sensor events. Each event carries readin

- **UUID:** `b202229b-72e6-4d7a-b964-6cca80d66970`
- **Slug:** `you-are-given-a-stream-of-multi-station-sensor-events-each-e`
- **Category:** machine-learning
- **Difficulty:** unknown

## Summary

You are given a stream of multi-station sensor events. Each event carries readings for a set of features (one per station) plus a target.

Stations come and go: a feature is out of schema when its cell is empty, and can start reporting later. Run one online ridge (recursive least squares) regressor whose dimension changes as features appear and disappear; report its predictions and retained state.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
