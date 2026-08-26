# I have a batch of one-dimensional quantum wells and I need the low-lying bound-s

Submission: `5f826675-34fb-488a-ae7d-b18f091ba670`  
Slug: `i-have-a-batch-of-one-dimensional-quantum-wells-and-i-need-t`  
Latest archive: `5f826675-34fb-488a-ae7d-b18f091ba670_submission_2026-07-10T18_57_14.606Z.zip`  
Revisions: 2

## Task summary

I have a batch of one-dimensional quantum wells and I need the low-lying bound-state energies for each of them. A well is a single particle in a potential V(x), governed by the time-independent equation -1/2 * psi''(x) + V(x) * psi(x) = E * psi(x) (hbar = m = 1)

Required artifacts include: `/app/data/potentials.json`, `/app/solve.dart`, `/app/energies.json`.

Author anonymous tagged this **hard** scientific-computing task (dart, numerical-methods, eigenvalue-problem, quantum-mechanics, scientific-computing).

Time estimates: expert ~120 min, junior ~300 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `5f826675-34fb-488a-ae7d-b18f091ba670_submission_2026-07-10T18_57_14.606Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
