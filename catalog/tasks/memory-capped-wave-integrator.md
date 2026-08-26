# # Memory-Capped Wave Integrator

Submission: `2d279cd7-0cc2-4696-b247-54885b07bce3`  
Slug: `memory-capped-wave-integrator`  
Latest archive: `2d279cd7-0cc2-4696-b247-54885b07bce3_submission_2026-07-06T07_22_27.345Z.zip`  
Revisions: 2

## Task summary

The Node integrator under `/app/` shows these symptoms in verifier workloads: The normal `run_entry.js` pipeline must regenerate traces from config; static or manual output writes are insufficient. Fix source code under `/app/` per the contract subsystem scope.

Required artifacts include: `/app/docs/pde_contract.md`, `/app/output_trace.json`, `/app/run_capped.sh`, `/app/run_entry.js`.

Author anonymous tagged this **hard** scientific-computing task (pde-solver, wave-equation, memory-constrained, stencil-methods, javascript, numerical-methods).

Time estimates: expert ~60 min, junior ~120 min.

Harbor timeouts: agent 900s, verifier 450s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `2d279cd7-0cc2-4696-b247-54885b07bce3_submission_2026-07-06T07_22_27.345Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
