# # Torus hex portal maze

Submission: `96483a4a-962e-497c-8316-6e8d168e9f20`  
Slug: `torus-hex-portal-maze`  
Latest archive: `96483a4a-962e-497c-8316-6e8d168e9f20_submission_2026-07-13T09_29_14.216Z.zip`  
Revisions: 4

## Task summary

The hex replay desk under `/app/environment` should rebuild `/app/output/ladder_replay_report.json` from graded maps in `/app/environment/fixtures/maps/` after `bash /app/environment/scripts/build_all.sh` and `bash /app/environment/scripts/run_ladder.sh`. Board orientation, edge remapping, portal entry arms, wet-rim costing, and replay digests are defined in `/app/environment/docs/h7_contract.md`. Public pointy samples such as `ridge_wrap` and `moss_trail` often look fine, but flat boards, arm-gated portals, wet rims after edge crossings, and wrap-then-portal packs drift: path stamps diverge, illegal portal entries fire (or legal ones do not), hop chains overshoot the goal, or `cost_total` disagrees with wet/portal tick rules. Training and puzzle trees are for probing only.

Required artifacts include: `/app/environment`, `/app/output/ladder_replay_report.json`, `/app/environment/fixtures/maps/`, `/app/environment/scripts/build_all.sh`, `/app/environment/scripts/run_ladder.sh`, `/app/environment/docs/h7_contract.md`.

Author anonymous tagged this **hard** games task (hex, maze, portal, torus, replay, games).

Time estimates: expert ~90 min, junior ~240 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `96483a4a-962e-497c-8316-6e8d168e9f20_submission_2026-07-13T09_29_14.216Z.zip` is a task submission, not a Harbor job. 4 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Game/engine behavior is mostly right but fails a replay, score, or state-hash test.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
