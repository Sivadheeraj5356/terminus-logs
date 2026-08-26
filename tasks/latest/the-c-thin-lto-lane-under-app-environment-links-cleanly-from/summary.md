# The C++ thin-LTO lane under `/app/environment` links cleanly from a wiped worksp

- **UUID:** `182c0859-2234-49a0-b664-dde068b9b37a`
- **Slug:** `the-c-thin-lto-lane-under-app-environment-links-cleanly-from`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

The C++ thin-LTO lane under `/app/environment` links cleanly from a wiped workspace, but incremental relinks can finish while `/app/work/bin/matrix_app` no longer matches a clean rebuild of the same profile state. Repair sources under `/app/environment` so incremental relinks keep summary sidecars, linked symbol sets, and binary probes aligned with generated headers and ABI stamps.

Output-only edits are insufficient. Pass scripts under `/app/environment/ci/harness/` must not disable thin LTO or force clean wipes on every incremental step.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
