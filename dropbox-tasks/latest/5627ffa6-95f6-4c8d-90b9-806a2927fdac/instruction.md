Post-hoc probability calibration for a multi-class classifier under distribution shift. Held-out inference bundles under /app/environment/data/ give raw confidences, hits, and subgroup lanes, plus a severity-ordered shift ladder with per-rung ECE budgets and strength-span limits, an optional rim used only when placing equal-mass reliability-diagram edges, and a required holdout fold used only for the emitted holdout witness. The evaluator under /app/environment must fit histogram, isotonic, and grouped-isotonic calibrators on the fit fold, measure expected calibration error (ECE) on each rung with sealed fit-plus-rim edges, and choose one calibration family per rung under budget, nondecreasing strength, and span limits.

Update the calibrator sources under /app/environment so a rebuilt binary produces evaluations that meet the calibration contract on every conforming bundle, including after fold refits and interrupted evaluation runs.

```
make -C /app/environment rebuild
/app/bin/plangen plan --input <bundle.json> --out <plan.json>
```

A document is accepted when there is one family per rung, ECE on that rung is at most budget times row count, every emitted confidence matches the chosen family's fit-fold map on that row, strengths never decrease with severity and never jump by more than that rung's span, and the plan's hold object reports each family's sealed-edge ECE on the holdout fold. Any feasible assignment is accepted.

Also emit the shipped order-sensitive evaluation to /app/out/plan.json.

```
/app/bin/plangen plan --input /app/environment/data/bundles/steep.json --out /app/out/plan.json
```

The plan object carries unit, bins, hold, and rungs; each rung record has severity, family, strength, deviation, allowance, and values. Model-evaluation role, arithmetic, family definitions, rim edges, ECE, span limits, schemas, and durable evaluation-state guidance are in /app/environment/docs/model-evaluation.md, /app/environment/docs/public-invariants.md, /app/environment/docs/contract.rst, /app/environment/docs/protocol.rst, /app/environment/docs/input-format.rst, and /app/environment/docs/plan-format.rst. Bundles under /app/environment/data/ are read-only. The checker rebuilds from source and scores held-out shift ladders it generates. A hand-written report, a post-edited report, or a fit tuned only to the shipped examples will not pass; the normal rebuild-and-plan pipeline must regenerate the artifacts.
