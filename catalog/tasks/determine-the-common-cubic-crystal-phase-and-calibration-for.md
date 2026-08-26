# Determine the common cubic crystal phase and calibration for the two diffraction

Submission: `196fc576-d7d7-4772-9e89-d6e02ad15939`  
Slug: `determine-the-common-cubic-crystal-phase-and-calibration-for`  
Latest archive: `196fc576-d7d7-4772-9e89-d6e02ad15939_submission_2026-07-18T15_23_50.111Z.zip`  
Revisions in Dropbox: 1

## Task summary

Determine the common cubic crystal phase and calibration for the two diffraction scans in a study. The command is `/app/bin/cubic-index --study STUDY_PATH --output OUTPUT_PATH`. The study format, reflection rules, feasibility conditions, objective order, canonical tie-breaking, JSON certificate, diagnostics, limits, and publication behavior are defined in `/app/CUBIC_DIFFRACTION_PROTOCOL.md`. Implement the scientific indexing calculation in `/app/src/indexer.rs`. The fixed parser and renderer will call `pub fn solve(study: &Study) -> Option<Plan>`. The JSON certificate includes the exact `optimal_count` and lowercase SHA-256 `digest` defined by the protocol. A valid result must be derived from the supplied study, handle the declared eight-peak-per-scan boundary within the time limit, and reproduce the same certificate on repeated runs. The bundled example writes `/app/result.json`; normal runs use the absolute path passed with `--output`.

Required artifacts include: `/app/bin/cubic-index`, `/app/CUBIC_DIFFRACTION_PROTOCOL.md`, `/app/src/indexer.rs`, `/app/result.json`.

Author anonymous tagged this **hard** scientific-computing task (crystallography, powder-diffraction, lattice-indexing, exact-optimization, metrology).

Time estimates: expert ~150 min, junior ~300 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `196fc576-d7d7-4772-9e89-d6e02ad15939_submission_2026-07-18T15_23_50.111Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
