# The command-line tool `formula-order` in `/app` decides which of two formula ver

- **UUID:** `b58913bd-5fea-48c7-82e8-543b46328334`
- **Slug:** `the-command-line-tool-formula-order-in-app-decides-which-of`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

The command-line tool `formula-order` in `/app` decides which of two formula versions is the newer one, so the catalog can keep a formula's published releases in order when it plans an upgrade or pins a dependency. Given two version strings on the command line, it prints -1 when the first is older than the second, 1 when the first is newer, and 0 when the two rank equally.

Today it only handles plain dotted-number releases, so it misranks most of the versions a real catalog publishes; it needs to order the full range of versions the way Homebrew itself orders formula versions. That ordering reaches well past comparing dotted numbers.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
