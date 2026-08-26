# # Vaccine cold-chain lot-wave planner

Submission: `a5dd6a73-2e23-40d3-9ced-545b33c975c1`  
Slug: `vaccine-cold-chain-lot-wave-planner`  
Latest archive: `a5dd6a73-2e23-40d3-9ced-545b33c975c1_submission_2026-07-19T07_25_05.929Z.zip`  
Revisions: 1

## Task summary

Scientific-computing vaccine cold-chain lot-wave planner. Immunolab fixtures under /app/data/immunolab/ and policy in /app/config/immuno.toml drive wave-3 allocation through the immunoflow planner at /app/environment. On the canonical chain, the public products under /app/output/ and persisted ledgers under /app/var/ disagree with each other and with independent replay of /app/environment/docs/contract.md. Implementation under /app/environment must be corrected so the normal immunoflow pipeline regenerates consistent artifacts. Rebuild per /app/environment/README.md, rerun the documented wave-3 chain, and fix Go and Rust library modules there, not only the CLI wrapper. Static or hand-written output is insufficient; fixture edits under /app/data/immunolab and wrapper-only shortcuts will not pass.

Required artifacts include: `/app/data/immunolab/`, `/app/config/immuno.toml`, `/app/environment`, `/app/output/`, `/app/var/`, `/app/environment/docs/contract.md`, `/app/environment/README.md`, `/app/data/immunolab`.

Author anonymous tagged this **hard** scientific-computing task (vaccine, epidemiology, cold-chain, simulation, allocation, planning).

Time estimates: expert ~240 min, junior ~600 min.

Harbor timeouts: agent 900s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `a5dd6a73-2e23-40d3-9ced-545b33c975c1_submission_2026-07-19T07_25_05.929Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
