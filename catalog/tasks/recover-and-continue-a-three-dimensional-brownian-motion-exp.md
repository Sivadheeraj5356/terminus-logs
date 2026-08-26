# Recover and continue a three-dimensional Brownian-motion experiment from particl

Submission: `90861d6b-54c0-493e-86f8-f17b71361d72`  
Slug: `recover-and-continue-a-three-dimensional-brownian-motion-exp`  
Latest archive: `90861d6b-54c0-493e-86f8-f17b71361d72_submission_2026-07-15T15_24_22.830Z.zip`  
Revisions in Dropbox: 1

## Task summary

Recover and continue a three-dimensional Brownian-motion experiment from particle records embedded in a partially corrupted Apptainer definition. The scientific work now has three stages: create a canonical laboratory checkpoint from an initial definition, resume that checkpoint when immutable prior shards are accompanied by new shards, and rebuild the DuckDB dataset and diffusion report from the checkpoint alone. The authoritative contract is `/app/environment/docs/diffusion-recovery-protocol.md`. Build the supplied offline Java/JDBC harness with `/app/environment/build.sh`. The entrypoint `/app/environment/run.sh` supports the documented `analyze`, `resume`, and `rebuild` modes. Successful runs create the requested canonical checkpoint when applicable, DuckDB dataset, and JSON report, and write exactly the report bytes to standard output.

Required artifacts include: `/app/environment/docs/diffusion-recovery-protocol.md`, `/app/environment/build.sh`, `/app/environment/run.sh`.

Author anonymous tagged this **hard** scientific-computing task (brownian, diffusion, checkpointing, jdbc, regression).

Time estimates: expert ~240 min, junior ~480 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `90861d6b-54c0-493e-86f8-f17b71361d72_submission_2026-07-15T15_24_22.830Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
