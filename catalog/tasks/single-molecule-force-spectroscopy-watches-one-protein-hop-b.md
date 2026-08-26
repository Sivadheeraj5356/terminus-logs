# Single-molecule force spectroscopy watches one protein hop between its folded an

Submission: `180fea04-64dd-4bb8-8419-2382dc6a9c48`  
Slug: `single-molecule-force-spectroscopy-watches-one-protein-hop-b`  
Latest archive: `180fea04-64dd-4bb8-8419-2382dc6a9c48_submission_2026-07-18T14_54_03.490Z.zip`  
Revisions: 5

## Task summary

Single-molecule force spectroscopy watches one protein hop between its folded and unfolded states while an optical trap holds it at a fixed load. Each hop is a diffusive crossing of the free-energy barrier, so the unfolding and folding rates measured at every load carry the shape of the landscape. Two things sit in the way: each molecule's bead and linker geometry shifts its attempt frequency, and each trap calibration misreads the load it actually applied, so the force that enters the rate is not the force on the dial. Neither is observed and both differ from molecule to molecule. /app/data/study.sqlite holds one study: landscape constants for this construct, twenty molecules, and unfolding and folding log-rates at five clamp forces each. The landscape, the passage-time definition of the two rates, the measurement model and the estimator the group settled on are written up in /app/MODEL.md. Standard ML is the working language here, /app/src carries a skeleton, and the native executable belongs at /app/bin/folding; the analysis stays in Standard ML rather than shelling out to another runtime.

Required artifacts include: `/app/data/study.sqlite`, `/app/MODEL.md`, `/app/src`, `/app/bin/folding`, `/app/output/report.json`, `/app/run.sh`.

Author Task Author tagged this **hard** scientific-computing task (sqlite, protein-folding, energy-landscape, kramers-rate, random-effects, single-molecule).

Time estimates: expert ~180 min, junior ~480 min.

Harbor timeouts: agent 1800.0s, verifier 1800.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `180fea04-64dd-4bb8-8419-2382dc6a9c48_submission_2026-07-18T14_54_03.490Z.zip` is a task submission, not a Harbor job. 5 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
