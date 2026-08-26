# Stellarbloom Season 9 prize desk is still mis-scoring banner pulls before weeken

Submission: `986ffe12-7ecb-4d08-bc89-157752212d0c`  
Slug: `stellarbloom-season-9-prize-desk-is-still-mis-scoring-banner`  
Latest archive: `986ffe12-7ecb-4d08-bc89-157752212d0c_submission_2026-07-16T12_57_03.097Z.zip`  
Revisions: 1

## Task summary

Stellarbloom Season 9 prize desk is still mis-scoring banner pulls before weekend payouts — the live fairness audit under `/app` has to match esports gacha policy. Note that code comments and docstrings may themselves contain errors. Get `/app/bin/gachaudit` writing a trustworthy `/app/output/report.json` for the stellarbloom export (side scripts that skip the desk binary do not count). CLI flags, schema, MAC domains, pity gap, revision dedupe, ledger keys, and anomaly kinds are in `/app/docs/prize_desk_contract.md`. Leave `/app/data/sessions.json` and `/app/config/gacha.json` unmodified.

Required artifacts include: `/app/bin/gachaudit`, `/app/output/report.json`, `/app/docs/prize_desk_contract.md`, `/app/data/sessions.json`, `/app/config/gacha.json`, `/app/docs/`.

Author anonymous tagged this **hard** games task (esports, lan-banner, provably-fair, pity-ledger, pull-commitment).

Time estimates: expert ~90.0 min, junior ~180.0 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `986ffe12-7ecb-4d08-bc89-157752212d0c_submission_2026-07-16T12_57_03.097Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Game/engine behavior is mostly right but fails a replay, score, or state-hash test.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
