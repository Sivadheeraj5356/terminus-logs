# Publish the Keeper's Canon content pack for Clockwork Crypt, a Lua terminal puzz

Submission: `a96d5a8b-488c-4392-9b00-c60a8895b5cf`  
Slug: `publish-the-keeper-s-canon-content-pack-for-clockwork-crypt`  
Latest archive: `a96d5a8b-488c-4392-9b00-c60a8895b5cf_submission_2026-07-17T16_20_19.603Z.zip`  
Revisions: 4

## Task summary

Publish the Keeper's Canon content pack for Clockwork Crypt, a Lua terminal puzzle adventure under `/app`. This is a game-content reconstruction challenge: use the designers' long-form lore journal to determine the adopted map, props, locks, character encounters, clue-card art, and staged twelve-beat finale. The finished adventure must let a player traverse the intended route, complete the adopted item-and-lock chain, meet every character in the intended state, perform the finale in order, and view the nine clue cards in their canonical atlas arrangement. `/app/docs/keeper_journal.md` is the authoritative game-design record; its closing construction identifies which earlier evidence leaves supply the adopted values, inherited identities, performance tuples, and art recipe. Clockwork Crypt stores its authored content through the existing four-file release history (`001_schema.lua` through `004_keeper_audit.lua`). Record the final canon in `004_keeper_audit.lua`, keep exactly four `migration_log` rows, and do not add a fifth migration. The released game state must contain exactly 11 rooms, 8 items, 8 locks, 7 NPCs, 9 clues, and 12 performance beats. Exits must be reciprocal and connected, while props, locks, encounters, and performance beats must form the journal's canonical gameplay relationships.

Required artifacts include: `/app/docs/keeper_journal.md`, `/app/bin/clockwork-crypt`, `/app/game/keeper_circuit.lua`, `/app/artifacts/keeper.circuit`, `/app/tools/build_atlas.sh`, `/app/bin/rebuild-world`, `/app/state/world.db`, `/app/artifacts/world.dump`.

Author anonymous tagged this **hard** games task (lua, interactive-fiction, puzzle-adventure, game-canon, worldbuilding, terminal-game, graph-search).

Time estimates: expert ~300 min, junior ~600 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `a96d5a8b-488c-4392-9b00-c60a8895b5cf_submission_2026-07-17T16_20_19.603Z.zip` is a task submission, not a Harbor job. 4 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Game/engine behavior is mostly right but fails a replay, score, or state-hash test.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
