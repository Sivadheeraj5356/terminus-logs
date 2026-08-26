# Our training engine at /app has a checkpoint/rematerialization mode that is supp

Submission: `6dabbf20-a99a-41dc-b50b-43f08707febb`  
Slug: `our-training-engine-at-app-has-a-checkpoint-rematerializatio`  
Latest archive: `6dabbf20-a99a-41dc-b50b-43f08707febb_submission_2026-07-17T11_54_13.501Z.zip`  
Revisions in Dropbox: 1

## Task summary

Our training engine at /app has a checkpoint/rematerialization mode that is supposed to be numerically indistinguishable from running without it, but right now checkpointed runs drift away from the baseline a few steps in, and resuming from a mid-run checkpoint doesn't line up with an uninterrupted run either. The engine is the stubbed Rust crate under /app/src. The op formulas, the per-layer rematerialization schedule, the PRNG and dataset-shuffling scheme, the ragged-last-batch rule, the optimizer update, and the gradient-clipping policy for the unstable third layer are all pinned in /app/spec/engine_design.md — read that first. Implement the tape-based autodiff engine and training loop so that a full run with checkpointing enabled reproduces the loss and gradient norm of the same run with checkpointing disabled at every step, and so that resuming from a checkpoint saved mid-run continues training identically to an uninterrupted run through the remaining steps. Don't change how the third layer behaves; clip its gradients per the spec rather than working around it. Write per-step loss, gradient norm, and checkpoint hashes into /app/out/runs.db following the schema in the spec, one row per step per run, for the non-checkpointed run, the checkpointed run, and the resumed run. Follow the RNG and batching rules exactly: small deviations in operation order or random-draw consumption desynchronize the run from the reference several steps later rather than immediately, so check your work past the first epoch boundary.

Required artifacts include: `/app/src`, `/app/spec/engine_design.md`, `/app/out/runs.db`.

Author anonymous tagged this **hard** machine-learning task (rust, autodiff, gradient-checkpointing, determinism, sqlite, numerical-computing).

Time estimates: expert ~240 min, junior ~1200 min.

Harbor timeouts: agent 1200.0s, verifier 450.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `6dabbf20-a99a-41dc-b50b-43f08707febb_submission_2026-07-17T11_54_13.501Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
