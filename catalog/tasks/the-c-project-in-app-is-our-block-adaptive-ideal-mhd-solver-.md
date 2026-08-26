# The C++ project in /app is our block-adaptive ideal-MHD solver, but the numerics

Submission: `064c4f2e-0120-40f7-aed0-1603c157de74`  
Slug: `the-c-project-in-app-is-our-block-adaptive-ideal-mhd-solver-`  
Latest archive: `064c4f2e-0120-40f7-aed0-1603c157de74_submission_2026-07-21T03_31_39.519Z.zip`  
Revisions in Dropbox: 2

## Task summary

The C++ project in /app is our block-adaptive ideal-MHD solver, but the numerics are unfinished. Finish it so that `make` in /app produces /app/bin/amr_mhd and that executable actually advances two-dimensional ideal magnetohydrodynamics with constrained transport on a two-level, block-adaptive Cartesian mesh, exactly as /app/docs/mhd-ct-spec.md lays out. The framework around the solver — the command line, the case and checkpoint formats, the equation-of-state helpers, the initial-condition presets, the time loop and the diagnostics — is already in place; what is stubbed out is the physics: the reconstruction and Riemann flux, the constrained-transport electric field, the coarse-fine synchronisation, the prolongation and restriction between levels, and the refinement criterion. Right now the stubbed core leaves the field frozen and never refines, so it meets none of the acceptance properties. The executable reads one case file (`--case`) and writes the reduced conserved and staggered fields, together with the conservation, positivity, divergence, refinement and restart diagnostics, to the JSON path given by `--out`, using exactly the schema, array shapes and cell and face ordering in the spec. It also writes and resumes from the checkpoint files named by `--checkpoint-out`/`--checkpoint-at` and `--restart`. The hidden cases it must handle are three-dimensional in the sense that they carry all three components of velocity and field; they include smooth Alfvén waves, advected field loops, magnetised blast waves, oblique shock tubes and diverging near-vacuum flows, run both...

Required artifacts include: `/app/bin/amr_mhd`, `/app/docs/mhd-ct-spec.md`.

Author anonymous tagged this **hard** scientific-computing task (magnetohydrodynamics, constrained-transport, adaptive-mesh-refinement, finite-volume, numerical-methods, cpp).

Time estimates: expert ~300 min, junior ~900 min.

Harbor timeouts: agent 1800.0s, verifier 1800.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `064c4f2e-0120-40f7-aed0-1603c157de74_submission_2026-07-21T03_31_39.519Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
