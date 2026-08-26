# Build /app/analysis.R for the Mice Protein Expression multiclass task. Read /app

- **UUID:** `21468c19-07d6-4a49-9133-90813ea846c9`
- **Slug:** `build-app-analysis-r-for-the-mice-protein-expression-multicl`
- **Category:** machine-learning
- **Difficulty:** hard

## Summary

Build /app/analysis.R for the Mice Protein Expression multiclass task. Read /app/data/train.csv and /app/config/model_config.json, preserve the supplied fit, validation, and test roles, and learn every preprocessing choice from fit rows only.

Use the closed-form one-vs-rest ridge score model described in /app/docs/07_model.txt, with softmax probabilities in the configured class order. Keep test labels out of model choice, preprocessing, lambda selection, and stability or refit decisions.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
