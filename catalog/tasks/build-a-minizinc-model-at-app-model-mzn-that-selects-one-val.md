# Build a MiniZinc model at /app/model.mzn that selects one valid rotamer at every

Submission: `d095b2e9-56c2-4fb5-8fca-f851e26df0c4`  
Slug: `build-a-minizinc-model-at-app-model-mzn-that-selects-one-val`  
Latest archive: `d095b2e9-56c2-4fb5-8fca-f851e26df0c4_submission_2026-07-17T03_06_00.552Z.zip`  
Revisions in Dropbox: 3

## Task summary

Build a MiniZinc model at /app/model.mzn that selects one valid rotamer at every protein residue and a compatible set of disulfide bridges. The design must satisfy composition, charge, mutation, clash, bridge-matching, and multistate stability requirements while minimizing the specified robust energy objective. The complete mathematical contract is in /app/contract.md, all input declarations are in /app/data_schema.mzn, and /app/output_contract.md defines the required JSON certificate. Solve /app/instance.dzn and keep all dimensions parameterized for same-schema instances.

Required artifacts include: `/app/model.mzn`, `/app/contract.md`, `/app/data_schema.mzn`, `/app/output_contract.md`, `/app/instance.dzn`.

Author anonymous tagged this **hard** scientific-computing task (optimization, protein-design, rotamers, disulfides, robust-design).

Time estimates: expert ~540 min, junior ~1620 min.

Harbor timeouts: agent 1800s, verifier 1800s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `d095b2e9-56c2-4fb5-8fca-f851e26df0c4_submission_2026-07-17T03_06_00.552Z.zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
