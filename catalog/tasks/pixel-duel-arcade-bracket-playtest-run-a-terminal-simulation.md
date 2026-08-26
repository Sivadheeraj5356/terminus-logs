# Pixel Duel arcade bracket playtest: run a terminal simulation game over rival ca

Submission: `ce5c0889-69d8-4058-aadd-5b6a68fb8e7a`  
Slug: `pixel-duel-arcade-bracket-playtest-run-a-terminal-simulation`  
Latest archive: `ce5c0889-69d8-4058-aadd-5b6a68fb8e7a_submission_2026-07-12T08_55_18.218Z.zip`  
Revisions in Dropbox: 1

## Task summary

Pixel Duel arcade bracket playtest: run a terminal simulation game over rival cabinet move logs so operators can seal win conditions before the next tournament tick. The working playfield under /app already ships rival move CSVs, the move-rule legality board seed, the in-sim referee oracle on loopback port 7088, and the deskctl playtest console in /app/booth. Implement the eight playtest planner kernels under the mod-* directories so deskctl regenerates seven deterministic bracket playtest atlases: /app/output/rival_merge.json, /app/output/referee_poll.json, /app/output/verdict_snapshots.json, /app/output/combo_audit.json, /app/output/bracket_seal.json, /app/output/rules_audit.json, and /app/output/fw_audit.json. Game simulation workflow, win-condition precedence, move legality, and digest recipes live in /app/docs/games-playtest-workflow.md, /app/docs/bracket_contract.md, /app/docs/move_rule_policy.md, /app/docs/firmware_policy.md, and /app/docs/lane_behavior_notes.md. Every atlas must be generated through deskctl playtest probes; static JSON files are not accepted.

Required artifacts include: `/app/booth`, `/app/output/rival_merge.json`, `/app/output/referee_poll.json`, `/app/output/verdict_snapshots.json`, `/app/output/combo_audit.json`, `/app/output/bracket_seal.json`, `/app/output/rules_audit.json`, `/app/output/fw_audit.json`.

Author anonymous tagged this **hard** games task (arcade-duel, playtest, bracket-sim, win-condition, move-rules, simulation).

Time estimates: expert ~180 min, junior ~420 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `ce5c0889-69d8-4058-aadd-5b6a68fb8e7a_submission_2026-07-12T08_55_18.218Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Game/engine behavior is mostly right but fails a replay, score, or state-hash test.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
