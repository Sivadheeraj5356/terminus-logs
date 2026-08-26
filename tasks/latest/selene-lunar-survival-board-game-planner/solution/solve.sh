#!/bin/bash
set -euo pipefail

cp /solution/main.go /workspace/task_file/main.go
cd /workspace
go run /workspace/task_file/main.go
