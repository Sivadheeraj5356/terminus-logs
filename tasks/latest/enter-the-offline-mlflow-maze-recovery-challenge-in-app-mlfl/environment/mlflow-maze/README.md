# MLflow Maze recovery kit

This directory contains the native recovery utility used by the Maze League's
offline level publisher. The tracking database follows the subset of the MLflow
SQLite schema documented in `docs/MLFLOW_STORE.md`; no MLflow server is needed.

Build with `make clean all`. The public command and game-state rules are defined
in `docs/RECOVERY_CONTRACT.md`. `scripts/recover-and-replay.sh` runs the seeded
recovery, validates the JSON Schema, and replays the committed walkthrough.
