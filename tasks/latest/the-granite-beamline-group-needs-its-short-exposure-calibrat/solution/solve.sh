#!/usr/bin/env bash
set -euo pipefail

cp /solution/beamline_oracle.js /app/main.js
cp /solution/beamline_oracle.js /app/task_file/beamline-tuner
chmod +x /app/task_file/beamline-tuner
