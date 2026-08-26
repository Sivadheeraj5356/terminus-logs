# The offline ReefBox reef-classifier rejects every capture because its deployment

- **UUID:** `c3861774-5884-4b89-b65d-9eae72836413`
- **Slug:** `the-offline-reefbox-reef-classifier-rejects-every-capture-be`
- **Category:** machine-learning
- **Difficulty:** hard

## Summary

The offline ReefBox reef-classifier rejects every capture because its deployment manifest is missing the per-device calibration embedded *inside* the PNG capture files. The deliverable is a single verified inference manifest at **`/app/out/inference_manifest.json`**, produced by running **`terraform apply`**.

The calibration format and every processing rule are undocumented except in the field notebook; this file specifies the deliverable and its output contract, and the notebook defines how each value is computed. The verifier runs `terraform apply` itself and checks the resulting manifest.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
