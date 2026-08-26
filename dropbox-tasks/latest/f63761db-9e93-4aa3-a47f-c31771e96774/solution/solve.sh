#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
install -m 0644 "$SCRIPT_DIR/mini_json.hpp" /app/workbench/mini_json.hpp
install -m 0644 "$SCRIPT_DIR/model.hpp" /app/workbench/model.hpp
install -m 0644 "$SCRIPT_DIR/model.cpp" /app/workbench/model.cpp
install -m 0644 "$SCRIPT_DIR/solver.hpp" /app/workbench/solver.hpp
install -m 0644 "$SCRIPT_DIR/solver.cpp" /app/workbench/solver.cpp
install -m 0644 "$SCRIPT_DIR/main.cpp" /app/workbench/main.cpp
make -C /app/workbench clean all
/app/bin/kirigami-map --input /app/cases/bench-01.json --output /app/results/oracle-smoke.json
