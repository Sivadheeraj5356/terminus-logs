# I'm working out how far a surface-catalysed batch reaction actually gets, run by

Submission: `0e01c492-0946-410a-9bda-28df1959c539`  
Slug: `i-m-working-out-how-far-a-surface-catalysed-batch-reaction-a`  
Latest archive: `0e01c492-0946-410a-9bda-28df1959c539_submission_2026-07-20T01_52_44.274Z.zip`  
Revisions in Dropbox: 1

## Task summary

I'm working out how far a surface-catalysed batch reaction actually gets, run by run, from time-lapse counts under the microscope. In each run a large batch of tagged reactant molecules starts adsorbed on the surface at time 0, and from there a molecule can convert to the product I care about, hit an irreversible side-reaction and decompose, or desorb and drift out of the field of view we can watch — and there's one more wrinkle in between: partway along a molecule can pass through a detectable activated intermediate, after which it both converts faster and desorbs faster, because the activated form is more reactive but more weakly held. That activation isn't a one-way step, though — the activated form is only loosely committed, so a fair fraction of it just relaxes back to the plain adsorbed state before doing anything else, and the two on-surface states keep trading population back and forth the whole time rather than draining in a single cascade. The product itself is not stuck in the patch either: once formed it can desorb and leave the field of view, so the product count we see is only the product that is still on the surface at that instant, not the cumulative number of molecules that have converted. What I need for each run is the cumulative conversion — the fraction of the whole starting batch that has become product by time t = 5 in the run's own time units. The catch is that the molecules that desorb don't stop reacting, they just leave the patch we can see, so they still go on to convert or decompose off-camera; and because the activated ones desorb fastest,...

Required artifacts include: `/app/reactor`.

Author anonymous tagged this **hard** scientific-computing task (reaction-kinetics, competing-pathways, reversible-kinetics, coupled-linear-ode, parameter-estimation, inverse-problem, ode-model-fitting, informative-loss, product-desorption).

Time estimates: expert ~300 min, junior ~660 min.

Harbor timeouts: agent 1800.0s, verifier 300.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `0e01c492-0946-410a-9bda-28df1959c539_submission_2026-07-20T01_52_44.274Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
