# Shuffleboard rink operators run a terminal playtest claim board under /app. The 

Submission: `9df3a13e-2ff9-435b-a5cf-1a8be0e69667`  
Slug: `shuffleboard-rink-operators-run-a-terminal-playtest-claim-bo`  
Latest archive: `9df3a13e-2ff9-435b-a5cf-1a8be0e69667_submission_2026-07-09T12_29_45.423Z.zip`  
Revisions: 2

## Task summary

Shuffleboard rink operators run a terminal playtest claim board under /app. The simulated court already loads layouts and wax-lot manifests. Your job is to finish the combinatorial planner so exclusive wax lanes are allotted under friction-band game rules and a sealed claim ledger is published for playtest review. The simulator must chalk an intermediate slate, then allot from that slate alone, and emit a deterministic claim ledger for the simulated match window. Contracts live in /app/docs/wax-lane-contract.md, /app/docs/chalk-slate.md, and /app/docs/cli-surface.md. Sample court fixtures live at these absolute paths:

Required artifacts include: `/app/docs/wax-lane-contract.md`, `/app/docs/chalk-slate.md`, `/app/docs/cli-surface.md`, `/app/data/rink-lanes.json`, `/app/data/disk-packages.json`, `/app/bin/waxlane-allot`, `/app/output/wax-lane-claim-ledger.json`, `/app/docs`.

Author anonymous tagged this **hard** games task (go, shuffleboard, wax, allotment, games, ledger).

Time estimates: expert ~180 min, junior ~420 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `9df3a13e-2ff9-435b-a5cf-1a8be0e69667_submission_2026-07-09T12_29_45.423Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Game/engine behavior is mostly right but fails a replay, score, or state-hash test.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
