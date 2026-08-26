# # Offline rescue chroot root rebind

- **UUID:** `61021cfc-efd5-4700-bac6-25fedf2e68fb`
- **Slug:** `offline-rescue-chroot-root-rebind`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

An offline rescue admin stack under /app/environment must rebind the active root into a staged chroot tree, keep a linker cache scoped to that tree, and materialize the minimal device node set each storage backend needs. Field rescue runs look close: interim tallies under /app/environment/fx_bins/interim/ stay plausible and single-profile smoke often passes, but full matrix grading still reports divergent digests after arena cycles and capability-mode flips.

The graded deliverable is /app/output/pack_trace.json. It must contain eight matrix rows for profiles silt, kite, rune, and dale under both capability modes cap_strict and cap_relaxed.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
