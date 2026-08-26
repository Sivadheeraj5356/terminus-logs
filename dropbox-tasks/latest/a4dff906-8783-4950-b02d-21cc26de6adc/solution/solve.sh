#!/usr/bin/env bash
set -Eeuo pipefail

solver_source=/solution/solve.go
published_source=/app/ferry_terminal_recovery_solver.go
solver_binary="$(mktemp -p /tmp ferry-recovery.XXXXXX)"
input_dir=/app/task_file/input_data
output_dir=/app/task_file/output_data

cleanup() {
    rm -f "$solver_binary"
}
trap cleanup EXIT

install -D -m 0644 "$solver_source" "$published_source"
/usr/local/go/bin/go build -trimpath -o "$solver_binary" "$solver_source"
mkdir -p "$output_dir"
"$solver_binary" "$input_dir" "$output_dir"

python3 - "$input_dir" "$output_dir" <<'PY'
import importlib.util
import sys
from pathlib import Path

input_path = sys.argv[1]
output_path = sys.argv[2]
model_path = Path("/app/task_file/scripts/model.py")
spec = importlib.util.spec_from_file_location("model", model_path)
model = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(model)
result = model.evaluate(input_path, output_path)
if result.get("penalty") or result.get("error") or result.get("total_score", 0.0) < 0.967:
    raise SystemExit(f"oracle self-validation failed: {result}")
print(f"oracle total_score={result['total_score']}")
PY
