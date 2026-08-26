#!/bin/bash
set -euo pipefail

go build -o /workspace/infer_stabilizer_burst_cosets /solution/main.go
/workspace/infer_stabilizer_burst_cosets \
  /workspace/task_file/stabilizer-burst-observations.json \
  /workspace/stabilizer-burst-coset-spectrum.json
