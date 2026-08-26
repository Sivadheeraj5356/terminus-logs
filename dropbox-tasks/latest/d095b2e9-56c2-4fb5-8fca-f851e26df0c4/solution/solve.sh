#!/usr/bin/env bash
set -euo pipefail

cp /solution/model_correct.mzn /app/model.mzn
/app/run_model.sh
