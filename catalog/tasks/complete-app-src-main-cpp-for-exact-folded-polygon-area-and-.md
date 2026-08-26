# Complete /app/src/main.cpp for exact folded-polygon area and moments.

Submission: `8824d7ea-ecc3-43dc-84c2-538720f26dc6`  
Slug: `complete-app-src-main-cpp-for-exact-folded-polygon-area-and-`  
Latest archive: `8824d7ea-ecc3-43dc-84c2-538720f26dc6_submission_2026-07-18T04_15_10.838Z.zip`  
Revisions in Dropbox: 1

## Task summary

Complete /app/src/main.cpp for exact folded-polygon area and moments. Legacy input is n, n counterclockwise integer vertices, then a b c defining a*x+b*y=c. S is the closed a*x+b*y<=c portion; F is the reflection of the a*x+b*y>=c portion. Output visible_area, double_covered_area, visible_x_moment, visible_y_moment, double_x_moment, and double_y_moment, where visible is S union F and double is S intersection F. Values are reduced rationals with positive denominators. Denominator one must be emitted as an integer; p/1 is invalid. Zero-area double regions still use six numeric fields.

Required artifacts include: `/app/src/main.cpp`.

Author anonymous tagged this **hard** scientific-computing task (scientific-computing, computational-geometry, exact-areas, folding, rational-output).

Time estimates: expert ~180 min, junior ~420 min.

Harbor timeouts: agent 1800.0s, verifier 1200.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `8824d7ea-ecc3-43dc-84c2-538720f26dc6_submission_2026-07-18T04_15_10.838Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
