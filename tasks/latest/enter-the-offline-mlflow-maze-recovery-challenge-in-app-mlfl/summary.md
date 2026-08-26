# Enter the offline MLflow Maze recovery challenge in `/app/mlflow-maze`. Its YAML

- **UUID:** `e3bb8fed-5fb2-490f-bf77-2181430d55dd`
- **Slug:** `enter-the-offline-mlflow-maze-recovery-challenge-in-app-mlfl`
- **Category:** games
- **Difficulty:** hard

## Summary

Enter the offline MLflow Maze recovery challenge in `/app/mlflow-maze`. Its YAML board and TOML puzzle catalog have lost rooms, exits, and prompts; competing revision chains in the MLflow-compatible SQLite tracking store contain the possible repairs.

Recover one complete playable level and publish `/app/mlflow-maze/out/level-manifest.json` through the supplied game console. `/app/mlflow-maze/docs/RECOVERY_CONTRACT.md` is the authoritative rulebook for eligible runs, patch chains, global branch selection, graph validity, and command outcomes.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
