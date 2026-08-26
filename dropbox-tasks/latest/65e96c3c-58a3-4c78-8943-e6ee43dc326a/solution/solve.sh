#!/bin/bash
set -euo pipefail
script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
exec /opt/test-venv/bin/python "$script_dir/solve_incident.py" "$@"
