#!/bin/bash
set -euo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
mkdir -p /app/out
python3 "$script_dir/build_fish_report.py" \
  --input /app/xwing-data/input/candidate_layouts.tsv \
  --targets /app/out/fish_targets.tsv \
  --ratings /app/out/fish_ratings.tsv \
  --summary /app/out/fish_summary.json
