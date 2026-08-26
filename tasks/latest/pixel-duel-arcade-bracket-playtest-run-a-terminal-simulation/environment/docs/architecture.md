# Playfield layout

Arcade Pixel Duel playtest simulation layout under `/app`:

- `/app/booth/` — deskctl playtest console entry used by probe ticks.
- `/app/mod-h7/`, `/app/mod-k9/`, `/app/mod-m3/`, `/app/mod-n4/`, `/app/mod-p2/`, `/app/mod-q1/`, `/app/mod-r8/`, `/app/mod-s2/` — playtest planner kernels for merge, referee poll, win-condition verdicts, combo ticks, seal, move-rule board audit, and firmware audit.
- `/app/svc/` — in-sim referee oracle listening on loopback port 7088 during playtest ticks.
- `/app/data/` — rival move CSV fixtures and move-rule board seed SQL.
- `/app/run/` — runtime playfield state including the materialized move-rule board after desk_init.
- `/app/output/` — sealed playtest atlas JSON snapshots.

## Playtest probe scripts

deskctl playtest ticks are driven by helper scripts under `/app/scripts/`:

- `/app/scripts/desk_init.sh` — materializes the move-rule board at `/app/run/move_rules.sqlite` from seed SQL.
- `/app/scripts/build_all.sh` — installs the deskctl playtest console wrapper that dispatches into `/app/booth`.
- `/app/scripts/ref_svc_start.sh` — starts the in-sim referee oracle on port 7088.
- `/app/scripts/milestone_probes.sh` — runs a named playtest tick (`ledgers`, `referee`, `verdicts`, `combos`, `seal`, `rules`, `fw`) that writes one atlas under `/app/output/`.

Primary workflow: `/app/docs/games-playtest-workflow.md`. Contracts: `/app/docs/bracket_contract.md`. Supplementary policy notes: `/app/docs/move_rule_policy.md`, `/app/docs/firmware_policy.md`, `/app/docs/lane_behavior_notes.md`.
