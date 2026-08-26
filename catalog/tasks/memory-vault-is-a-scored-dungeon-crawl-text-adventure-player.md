# Memory Vault is a scored dungeon-crawl text adventure. Players walk rooms,

Submission: `282b53e2-9b37-4be3-9ec1-548e08817733`  
Slug: `memory-vault-is-a-scored-dungeon-crawl-text-adventure-player`  
Latest archive: `282b53e2-9b37-4be3-9ec1-548e08817733_submission_2026-07-21T18_43_03.857Z.zip`  
Revisions in Dropbox: 2

## Task summary

Memory Vault is a scored dungeon-crawl text adventure. Players walk rooms, TAKE and DROP items, WAIT to ready a seal, SEAL watched chambers, SCRUB leak chambers, and EXIT with the key for WIN, LOSE, or PARTIAL endings. Campaign playthrough scripts live under `/app/environment/cases`. The adventure under `/app/environment` must score those playthroughs using the live chamber ledgers in `/app/environment/traces/` and write the campaign scoreboard: `/app/output/transcripts/<case_id>.json`, `/app/output/state/hazard.epoch`, `/app/output/state/replay.journal`, and `/app/output/batch.manifest.json`. Start play with `/app/environment/campaign/play.sh`.

Required artifacts include: `/app/environment/cases`, `/app/environment`, `/app/environment/traces/`, `/app/output/transcripts/`, `/app/output/state/hazard.epoch`, `/app/output/state/replay.journal`, `/app/output/batch.manifest.json`, `/app/environment/campaign/play.sh`.

Author anonymous tagged this **hard** games task (text-adventure, dungeon-crawl, inventory, scoring, win-lose, puzzle).

Time estimates: expert ~180 min, junior ~360 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `282b53e2-9b37-4be3-9ec1-548e08817733_submission_2026-07-21T18_43_03.857Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Game/engine behavior is mostly right but fails a replay, score, or state-hash test.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
