# A computational fluid dynamics lab stages two finite-volume Burgers simulation c

Submission: `1565061a-c79b-44e5-8a5e-7c292052ef33`  
Slug: `a-computational-fluid-dynamics-lab-stages-two-finite-volume-`  
Latest archive: `1565061a-c79b-44e5-8a5e-7c292052ef33_submission_2026-07-11T08_09_25.572Z.zip`  
Revisions in Dropbox: 1

## Task summary

A computational fluid dynamics lab stages two finite-volume Burgers simulation consumable kits across a season of shock-capture and flux-calibration campaigns. Weekly simulation demand for each kit is known in advance; purchase prices move week to week. Stock carries forward in a shared cold store, each week's runs are met from stock on hand, and end-of-week inventory for every kit must stay at or above that kit's safety reserve `smin[p]` in every week. Kits differ in refrigerated-truck volume; instance capacity `B` limits volume per run. The lab may keep trucks on the books for the season or call outside hauliers when weekly demand exceeds owned capacity. Fleet, holding, peak, and shock-capture fees are documented under `/app/docs`, `/app/consumables`, and `/app/facilities`. Procurement indexes and finance worksheets in those trees may disagree—reconcile before modelling. Inventory balance and reserve rules are in `/app/consumables/handling.md`.

Required artifacts include: `/app/docs`, `/app/consumables`, `/app/facilities`, `/app/consumables/handling.md`, `/app/model.mzn`, `/app/instance.dzn`, `/app/docs/output_format.md`, `/app/docs/data_dictionary.md`.

Author anonymous tagged this **medium** scientific-computing task (optimization, operations-research, constraint-programming, minizinc, finite-volume, computational-fluid-dynamics).

Time estimates: expert ~200 min, junior ~400 min.

Harbor timeouts: agent 1800.0s, verifier 1800.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `1565061a-c79b-44e5-8a5e-7c292052ef33_submission_2026-07-11T08_09_25.572Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
