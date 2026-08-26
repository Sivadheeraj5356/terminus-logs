# Fabert is a ChaLearn wide-table multiclass dataset with 800 numeric features and

- **UUID:** `f5e0f8cb-40da-4dfb-81fe-891f2a26cb15`
- **Slug:** `fabert-is-a-chalearn-wide-table-multiclass-dataset-with-800`
- **Category:** machine-learning
- **Difficulty:** hard

## Summary

Fabert is a ChaLearn wide-table multiclass dataset with 800 numeric features and labels 0 through 6. Update /app/analysis.R in place so a clean run reads labelled training rows from DATA_DIR/fabert_train.csv, default DATA_DIR=/app/data, scores unlabelled rows from DATA_DIR/fabert_score.csv, and recreates every deliverable under OUT_DIR, default /app/outputs.

Use the provided row_id column as the stable source row id and class order 0,1,2,3,4,5,6. Produce scored predictions, class probabilities, and a class-weight audit.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
