# After a stacked cache tier was relocated onto a new backing origin, operators ma

- **UUID:** `773fb6bc-dffe-4ba5-a68f-bdb780bcee46`
- **Slug:** `after-a-stacked-cache-tier-was-relocated-onto-a-new-backing`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

After a stacked cache tier was relocated onto a new backing origin, operators materialize scratch workspaces with the `cvctl` tree under `/app/environment`. Mapped-slot rereads may still serve older fast-lane payloads while authority surfaces converge.

Tap tallies can advance during an open relocation window. Operator artifacts may report a settled posture while origin alias, active ref, promotion seal, or quorum witnesses still lag the post-move origin.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
