#!/usr/bin/env bash
set -euo pipefail

minizinc --solver highs --output-mode json --output-objective /app/model.mzn /app/instance.dzn
