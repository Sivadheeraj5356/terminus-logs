# # Torus hex portal maze

- **UUID:** `96483a4a-962e-497c-8316-6e8d168e9f20`
- **Slug:** `torus-hex-portal-maze`
- **Category:** games
- **Difficulty:** hard

## Summary

The hex replay desk under `/app/environment` should rebuild `/app/output/ladder_replay_report.json` from graded maps in `/app/environment/fixtures/maps/` after `bash /app/environment/scripts/build_all.sh` and `bash /app/environment/scripts/run_ladder.sh`. Board orientation, edge remapping, portal entry arms, wet-rim costing, and replay digests are defined in `/app/environment/docs/h7_contract.md`.

Public pointy samples such as `ridge_wrap` and `moss_trail` often look fine, but flat boards, arm-gated portals, wet rims after edge crossings, and wrap-then-portal packs drift: path stamps diverge, illegal portal entries fire (or legal ones do not), hop chains overshoot the goal, or `cost_total` disagrees with wet/portal tick rules. Training and puzzle trees are for probing only.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
