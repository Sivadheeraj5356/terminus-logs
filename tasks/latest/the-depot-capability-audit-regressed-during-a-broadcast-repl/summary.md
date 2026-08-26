# The depot capability audit regressed during a broadcast replay and key-epoch rol

- **UUID:** `4f49822b-f0b0-4cc4-b748-2a76e3d8670d`
- **Slug:** `the-depot-capability-audit-regressed-during-a-broadcast-repl`
- **Category:** security
- **Difficulty:** hard

## Summary

The depot capability audit regressed during a broadcast replay and key-epoch roll. Operators now see different admission traces for equivalent pack orderings, stale session rows disappear across rebuilds, alias-presented tickets disagree with canonical subjects, and revocation clears do not always take effect at their visible row sequence.

The working source tree is `/app/environment`. The normal pipeline is `bash /app/environment/ci/rebuild.sh` plus `/app/environment/bin/depot audit --pack <pack>`, with `/app/output/admission_trace.json` as the regenerated trace.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
