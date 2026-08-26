# # Game balance archaeology

Submission: `bac889e0-9c8d-413d-8916-6c4bd405a5a5`  
Slug: `game-balance-archaeology`  
Latest archive: `bac889e0-9c8d-413d-8916-6c4bd405a5a5_submission_2026-07-16T07_29_56.570Z.zip`  
Revisions: 1

## Task summary

The live-ops desk archived years of competitive telemetry through a Go pipeline under `/app/environment`, but exports no longer line up with design reviews. Era windows look calendar-driven, actor rates disagree with match volumes, and the stamped archive seal fails audit replay. Repair sources under `/app/environment`, rebuild with `make -C /app/environment all`, and regenerate `/app/output/balance_archive.json` through `/opt/simbin/balancectl` per `/app/environment/docs/cli_invocation.txt`. Binding formulas live in `/app/environment/docs/balance_contract.md`. The regenerated archive must follow that contract, including schema_version, scenario, eras, turning_points, recommendations, archive_digest, and era-row dominant_win_lower values. A 2019 design memo may describe the wrong calendar windowing. Validate with `/tests/test.sh`.

Required artifacts include: `/app/environment`, `/app/output/balance_archive.json`, `/app/environment/docs/cli_invocation.txt`, `/app/environment/docs/balance_contract.md`.

Author anonymous tagged this **hard** data-processing task (data-processing, balance, telemetry, live-ops, archaeology).

Time estimates: expert ~150 min, junior ~420 min.

Harbor timeouts: agent 1800s, verifier 1200s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `bac889e0-9c8d-413d-8916-6c4bd405a5a5_submission_2026-07-16T07_29_56.570Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
