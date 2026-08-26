# The simultaneous-turn fog engine under `/app/environment` is not meeting its cas

Submission: `efaddcc7-6bd8-416d-a977-aee50d2a7e18`  
Slug: `the-simultaneous-turn-fog-engine-under-app-environment-is-no`  
Latest archive: `efaddcc7-6bd8-416d-a977-aee50d2a7e18_submission_2026-07-19T13_16_02.623Z.zip`  
Revisions in Dropbox: 1

## Task summary

The simultaneous-turn fog engine under `/app/environment` is not meeting its case ladder yet. Repair TypeScript modules under `/app/environment` so digest, mix, and certificate helpers match the published rules and the play pipeline regenerates correct artifacts. From `/app/environment` run

Required artifacts include: `/app/environment`, `/app/environment/fixtures/cases.toml`, `/app/output/sheet.json`, `/app/output/vlog.jsonl`, `/app/environment/docs/k_rules.md`, `/app/environment/docs/sheet.schema.json`, `/app/environment/docs/vlog.schema.json`.

Author anonymous tagged this **hard** games task (typescript, games, fog-of-war, simultaneous-turns, engine, board).

Time estimates: expert ~150 min, junior ~420 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `efaddcc7-6bd8-416d-a977-aee50d2a7e18_submission_2026-07-19T13_16_02.623Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Game/engine behavior is mostly right but fails a replay, score, or state-hash test.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
