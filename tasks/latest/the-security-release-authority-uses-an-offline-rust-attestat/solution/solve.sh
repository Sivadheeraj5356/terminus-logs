#!/bin/bash
set -euo pipefail

cp /solution/solver_main.rs /app/task_file/logseal/src/main.rs
cd /app/task_file/logseal
cargo build --release --locked
