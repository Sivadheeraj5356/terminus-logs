# Pixel Duel arcade bracket playtest: run a terminal simulation game over rival ca

- **UUID:** `ce5c0889-69d8-4058-aadd-5b6a68fb8e7a`
- **Slug:** `pixel-duel-arcade-bracket-playtest-run-a-terminal-simulation`
- **Category:** games
- **Difficulty:** hard

## Summary

Pixel Duel arcade bracket playtest: run a terminal simulation game over rival cabinet move logs so operators can seal win conditions before the next tournament tick. The working playfield under /app already ships rival move CSVs, the move-rule legality board seed, the in-sim referee oracle on loopback port 7088, and the deskctl playtest console in /app/booth.

Implement the eight playtest planner kernels under the mod-* directories so deskctl regenerates seven deterministic bracket playtest atlases: /app/output/rival_merge.json, /app/output/referee_poll.json, /app/output/verdict_snapshots.json, /app/output/combo_audit.json, /app/output/bracket_seal.json, /app/output/rules_audit.json, and /app/output/fw_audit.json. Game simulation workflow, win-condition precedence, move legality, and digest recipes live in /app/docs/games-playtest-workflow.md, /app/docs/bracket_contract.md, /app/docs/move_rule_policy.md, /app/docs/firmware_policy.md, and /app/docs/lane_behavior_notes.md.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
