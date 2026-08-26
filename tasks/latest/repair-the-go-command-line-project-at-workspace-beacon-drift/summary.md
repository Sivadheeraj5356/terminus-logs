# Repair the Go command-line project at /workspace/beacon-drift-go-build-rescue so

- **UUID:** `6eb2b426-ed78-4ec2-a060-4038a99d33ea`
- **Slug:** `repair-the-go-command-line-project-at-workspace-beacon-drift`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

Repair the Go command-line project at /workspace/beacon-drift-go-build-rescue so it behaves like a dependable offline release package for coastal operations staff. A fresh checkout must support the ordinary make workflow for cleaning, testing, building, and smoke verification without downloading anything, while keeping the module small and under its existing project identity.

The test workflow should exercise the whole project, including internal packages, not only the command entry point. Operators build a command named beacon-drift, copy it to field laptops, and run it with a named operating profile, a packet file, and a report destination.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
