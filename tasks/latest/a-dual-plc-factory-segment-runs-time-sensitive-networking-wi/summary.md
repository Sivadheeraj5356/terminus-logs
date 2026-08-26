# A dual-PLC factory segment runs Time-Sensitive Networking with scheduled gate co

- **UUID:** `51fbf555-d1d9-40db-b47b-1d8a4770784d`
- **Slug:** `a-dual-plc-factory-segment-runs-time-sensitive-networking-wi`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

A dual-PLC factory segment runs Time-Sensitive Networking with scheduled gate control across three switches, a redundant cross-link, and asymmetric bottlenecks under maintenance derating. Topology, gate schedules, traffic classes, periodic message flows, clock synchronization offsets, packet traces, and the TSN profile overview live under `/app/data/`.

Behavioral rules — WCET composition, compliance deadlines derived from traffic-class shaving in `traffic_classes.json`, queue guard bands on gate schedules, bandwidth reservation with per-flow overhead bytes, switch-only clock-skew accumulation with trace jitter, trace miss deduplication when clock skew supersedes observed misses, scheduling-exempt flows, gate-window conflicts, priority-inversion detection, trace validation filtering, metric formulas, and output schemas — are defined in `/app/data/validation_policy.json`. When the overview in `tsn_profile.json` disagrees with the policy or bundled inputs, follow the policy.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
