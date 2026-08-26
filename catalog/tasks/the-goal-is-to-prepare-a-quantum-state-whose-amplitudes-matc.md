# The goal is to prepare a quantum state whose amplitudes match a supplied real pr

Submission: `73a7d8dd-cdc8-4b15-8390-5a3740b19f39`  
Slug: `the-goal-is-to-prepare-a-quantum-state-whose-amplitudes-matc`  
Latest archive: `73a7d8dd-cdc8-4b15-8390-5a3740b19f39_submission_2026-07-19T09_41_40.550Z.zip`  
Revisions in Dropbox: 1

## Task summary

The goal is to prepare a quantum state whose amplitudes match a supplied real profile. A solution reads a specification and emits a circuit that builds the requested state on a register starting in the all zeros state. The specification is a text file. Its first line holds a width n. The next two to the power n lines each hold one nonnegative decimal number, the amplitudes in index order, already normalized so the sum of their squares equals one. A final line begins with the letter B followed by an integer budget.

Required artifacts include: `/app/submission.rs`.

Author anonymous tagged this **medium** scientific-computing task (quantum, state-preparation, amplitude-encoding, openqasm, controlled-rotation).

Time estimates: expert ~120 min, junior ~300 min.

Harbor timeouts: agent 600s, verifier 600s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `73a7d8dd-cdc8-4b15-8390-5a3740b19f39_submission_2026-07-19T09_41_40.550Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
