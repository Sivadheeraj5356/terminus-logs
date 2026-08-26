#!/bin/bash
set -euo pipefail

DEFAULT_API_URL="http://127.0.0.1:8000/api/v1"
DEFAULT_TRAINING_DATA="/app/data/training.parquet"
DEFAULT_ARTIFACTS_DIR="/app/artifacts"

print_help() {
  cat <<'HELP'
Usage: /app/p/wf <command> [options]

Commands:
  train      Train and package the classifier
  run-drift  Score an inference batch and submit drift evidence
HELP
}
