# An on-call reliability engineer is deciding whether a degraded stateful service

- **UUID:** `403fcd7c-b947-492d-a268-d2992e87485f`
- **Slug:** `an-on-call-reliability-engineer-is-deciding-whether-a-degrad`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

An on-call reliability engineer is deciding whether a degraded stateful service group may move to a standby host without split-brain writes, exposed held services, or a lost rollback path. The incident evidence is under `/app/records`, the authoritative operating rules are in `/app/README.md`, and the completed failover readiness dossier must live under `/app/dossier`.

The dossier has exactly sixteen artifacts across `/app/dossier/decision`, `/app/dossier/evidence`, `/app/dossier/attestations`, and `/app/dossier/index`; each artifact must describe the same incident epoch, service group, selected host, evidence basis, and safety conclusion. Place an executable operational assessment entrypoint at `/app/solve.sh`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
