# Trickfall Matchbook Arena

Submission: `4cef8e9c-2a77-43cf-8668-59551b8543e0`  
Slug: `trickfall-matchbook-arena`  
Latest archive: `4cef8e9c-2a77-43cf-8668-59551b8543e0_submission_2026-07-17T16_40_37.944Z.zip`  
Revisions in Dropbox: 1

## Task summary

Trickfall Matchbook Arena Create `/app/matchbook/matchbook`, an offline Rust command-line analyst for adversarial Trickfall endgames. Its interface is `./matchbook solve FILE`, where FILE follows the matchbook protocol at `/app/matchbook/spec.md` and may contain several independent cases.

Required artifacts include: `/app/matchbook/matchbook`, `/app/matchbook/spec.md`.

Author anonymous tagged this **hard** games task (rust, terminal-game, game-tree-search, trick-taking, adversarial-planning).

Time estimates: expert ~300 min, junior ~720 min.

Harbor timeouts: agent 1800.0s, verifier 1800.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `4cef8e9c-2a77-43cf-8668-59551b8543e0_submission_2026-07-17T16_40_37.944Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Game/engine behavior is mostly right but fails a replay, score, or state-hash test.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
