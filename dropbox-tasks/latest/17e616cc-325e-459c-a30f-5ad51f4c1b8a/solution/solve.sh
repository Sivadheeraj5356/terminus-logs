#!/usr/bin/env bash
set -euo pipefail

cp /solution/main.go /app/task_file/src/main.go
make -C /app/task_file clean
make -C /app/task_file
