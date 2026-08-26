# Tower defense live-ops wants a trustworthy wave-balancer certificate for publish

Submission: `d2275740-d918-44f9-9a98-0b0623dd7865`  
Slug: `tower-defense-live-ops-wants-a-trustworthy-wave-balancer-cer`  
Latest archive: `d2275740-d918-44f9-9a98-0b0623dd7865_submission_2026-07-15T08_00_38.480Z (1).zip`  
Revisions: 2

## Task summary

Tower defense live-ops wants a trustworthy wave-balancer certificate for published pressure. Do not hand-author `/app/output/feasibility_cert.json`.

Required artifacts include: `/app/output/feasibility_cert.json`, `/app/environment`, `/app/environment/drv/run_td.sh`, `/app/environment/data/m9`, `/app/environment/data/z2`, `/app/environment/pol/cap.toml`, `/app/environment/pol/q_floor.json`, `/app/environment/docs/abi_notes.md`.

Author anonymous tagged this **hard** games task (tower-defense, wave-balance, feasibility-certificate, schedule-search, java, offline-sim).

Time estimates: expert ~90 min, junior ~240 min.

Harbor timeouts: agent 900s, verifier 450s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `d2275740-d918-44f9-9a98-0b0623dd7865_submission_2026-07-15T08_00_38.480Z (1).zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Game/engine behavior is mostly right but fails a replay, score, or state-hash test.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
