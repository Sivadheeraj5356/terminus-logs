Pixel Duel arcade bracket playtest: run a terminal simulation game over rival cabinet move logs so operators can seal win conditions before the next tournament tick. The working playfield under /app already ships rival move CSVs, the move-rule legality board seed, the in-sim referee oracle on loopback port 7088, and the deskctl playtest console in /app/booth. Implement the eight playtest planner kernels under the mod-* directories so deskctl regenerates seven deterministic bracket playtest atlases: /app/output/rival_merge.json, /app/output/referee_poll.json, /app/output/verdict_snapshots.json, /app/output/combo_audit.json, /app/output/bracket_seal.json, /app/output/rules_audit.json, and /app/output/fw_audit.json.

Game simulation workflow, win-condition precedence, move legality, and digest recipes live in /app/docs/games-playtest-workflow.md, /app/docs/bracket_contract.md, /app/docs/move_rule_policy.md, /app/docs/firmware_policy.md, and /app/docs/lane_behavior_notes.md. Every atlas must be generated through deskctl playtest probes; static JSON files are not accepted.

Signal completion when all seven atlases under /app/output are present and regenerate deterministically through deskctl.

Hidden verifier fixtures under /opt/verifier-fixtures/ supply alternate rival move logs and firmware policy inputs for additional playtest probes documented in /app/docs/lane_behavior_notes.md.

Do not write static JSON under /app/output by hand. Prefer deskctl probes so each playtest atlas stays regenerable.

Decoy helpers under /app/lib/decoy are indexing aids only and must stay off the snapshot hot path.
