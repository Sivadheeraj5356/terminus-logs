# This is a numerical computation in exact linear algebra, the reconstruction of a

Submission: `5884bca2-ccbc-41c9-90a4-999040938b95`  
Slug: `this-is-a-numerical-computation-in-exact-linear-algebra-the`  
Latest archive: `5884bca2-ccbc-41c9-90a4-999040938b95_submission_2026-07-13T16_33_24.615Z (1).zip`  
Revisions: 3

## Task summary

This is a numerical computation in exact linear algebra, the reconstruction of a univariate polynomial from a scheme of derivative conditions. Each problem fixes a degree bound N, so the unknown polynomial has N coefficients and degree below N, together with a list of conditions. Every condition is three integers, a point x, a derivative order j, and a value v, and it asks that the j-th derivative of the polynomial at x equal v, with the zeroth derivative being the value itself. The conditions are not required to be nicely shaped. The derivative orders at a point need not be contiguous, so a point may fix its value and its second derivative while saying nothing about its first; a point may fix only a derivative and never its value; the same point and order may appear more than once; and the number of conditions may fall short of N, equal it, or exceed it. A problem may therefore have exactly one polynomial of degree below N that meets every condition, or none at all, or more than one.

Required artifacts include: `/app/docs`.

Author anonymous tagged this **hard** scientific-computing task (exact-linear-algebra, birkhoff-interpolation, lacunary-scheme, rank-and-consistency, arbitrary-precision, derivative-conditions).

Time estimates: expert ~420 min, junior ~960 min.

Harbor timeouts: agent 1800s, verifier 1800s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `5884bca2-ccbc-41c9-90a4-999040938b95_submission_2026-07-13T16_33_24.615Z (1).zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
