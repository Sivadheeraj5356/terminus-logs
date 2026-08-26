# Drydock packaging for the Keelmark keel-block load console will not build. The c

- **UUID:** `c6ccb710-577e-4680-8bd5-bd8a7f589007`
- **Slug:** `drydock-packaging-for-the-keelmark-keel-block-load-console-w`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

Drydock packaging for the Keelmark keel-block load console will not build. The console is a multi-package Cabal workspace under /app, and during a rushed toolchain migration its packaging metadata drifted and three maintained modules never landed under the shipped source trees: Keelmark.Scan, Keelmark.Classify, and Keelmark.Emit exist only as retired 8.10-era copies under each package's compat tree.

Types and Main under src/app are intact; Scan, Classify, and Emit must be restored under the maintained src trees so they match the normative ledger, not the tide sheet. Harbor ops needs the packaging restored and those modules reconstituted so the console builds offline and the packaging gate runs before the next flood-tide window.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
