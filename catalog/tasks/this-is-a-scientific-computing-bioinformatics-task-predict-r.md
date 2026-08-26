# This is a scientific-computing bioinformatics task: predict RNA secondary struct

Submission: `fc31f5ee-7fc4-424f-999c-89dc3ac48a58`  
Slug: `this-is-a-scientific-computing-bioinformatics-task-predict-r`  
Latest archive: `fc31f5ee-7fc4-424f-999c-89dc3ac48a58_submission_2026-07-14T17_04_12.625Z.zip`  
Revisions in Dropbox: 1

## Task summary

This is a scientific-computing bioinformatics task: predict RNA secondary structure under the RNPX-12 folding model. RNPX-12 scores folded RNA structures using thermodynamic parameters, chemical-probing reactivity, and guide-channel evidence. For each RNA instance, determine the maximum-scoring secondary structure and report the scientific audit records required by `/app/docs/model_reference.md`.

Required artifacts include: `/app/docs/model_reference.md`, `/app/input_data/rna_public.txt`, `/app/thermo`, `/app/src/fold.cpp`.

Author anonymous tagged this **hard** scientific-computing task (computational-biology, bioinformatics, rna-folding, secondary-structure, thermodynamics, chemical-probing).

Time estimates: expert ~480.0 min, junior ~2400.0 min.

Harbor timeouts: agent 1200.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `fc31f5ee-7fc4-424f-999c-89dc3ac48a58_submission_2026-07-14T17_04_12.625Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
