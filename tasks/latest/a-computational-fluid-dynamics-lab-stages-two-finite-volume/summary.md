# A computational fluid dynamics lab stages two finite-volume Burgers simulation c

- **UUID:** `1565061a-c79b-44e5-8a5e-7c292052ef33`
- **Slug:** `a-computational-fluid-dynamics-lab-stages-two-finite-volume`
- **Category:** scientific-computing
- **Difficulty:** medium

## Summary

A computational fluid dynamics lab stages two finite-volume Burgers simulation consumable kits across a season of shock-capture and flux-calibration campaigns. Weekly simulation demand for each kit is known in advance; purchase prices move week to week.

Stock carries forward in a shared cold store, each week's runs are met from stock on hand, and end-of-week inventory for every kit must stay at or above that kit's safety reserve `smin[p]` in every week. Kits differ in refrigerated-truck volume; instance capacity `B` limits volume per run.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
