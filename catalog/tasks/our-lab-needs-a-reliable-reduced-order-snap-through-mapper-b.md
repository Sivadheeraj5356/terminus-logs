# Our lab needs a reliable reduced-order snap-through mapper before the next kirig

Submission: `f63761db-9e93-4aa3-a47f-c31771e96774`  
Slug: `our-lab-needs-a-reliable-reduced-order-snap-through-mapper-b`  
Latest archive: `f63761db-9e93-4aa3-a47f-c31771e96774_submission_2026-07-16T10_31_02.646Z.zip`  
Revisions in Dropbox: 8

## Task summary

Our lab needs a reliable reduced-order snap-through mapper before the next kirigami test series. Put the C++ implementation in `/app/workbench/main.cpp`, `/app/workbench/model.cpp`, and `/app/workbench/solver.cpp`, with any required headers beside them. Those sources must compile into an executable supporting `--input <absolute JSON path>` and `--output <absolute JSON path>`. It must evaluate any campaign allowed by `/app/docs/analysis-contract.md`; the files in `/app/cases` are only sanity checks and are not the complete input set. For a valid campaign, publish the complete equilibrium catalog at each requested load, every smooth limit point in the model domain, and the quasi-static sweep histories defined by the contract. Preserve the campaign identifier, use the report schema and deterministic ordering in the contract, emit only finite JSON numbers, and keep every field at its stated JSON type. A valid run exits 0 and atomically replaces the requested output.

Required artifacts include: `/app/workbench/main.cpp`, `/app/workbench/model.cpp`, `/app/workbench/solver.cpp`, `/app/docs/analysis-contract.md`, `/app/cases`, `/app/docs`.

Author anonymous tagged this **hard** scientific-computing task (nonlinear-mechanics, continuation, hysteresis, root-finding, kirigami).

Time estimates: expert ~180 min, junior ~420 min.

Harbor timeouts: agent 1800s, verifier 600s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `f63761db-9e93-4aa3-a47f-c31771e96774_submission_2026-07-16T10_31_02.646Z.zip` is a task submission, not a Harbor job. 8 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
