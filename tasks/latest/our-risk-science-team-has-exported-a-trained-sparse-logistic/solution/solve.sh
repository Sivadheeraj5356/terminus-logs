#!/usr/bin/env bash
set -euo pipefail

cp "$(dirname "$0")/calibrator.py" /app/task_file/calibrator.py
python3 /app/task_file/calibrator.py /app/task_file
