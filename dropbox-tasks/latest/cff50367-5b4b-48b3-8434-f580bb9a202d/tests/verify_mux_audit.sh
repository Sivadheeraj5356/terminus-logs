#!/bin/bash
# Verifier-owned mux entrypoint. Implementation lives in verify_mux_lib.py so
# grading rebuilds and runs the binary without trusting agent wrappers.
set -euo pipefail
exec /opt/verifier-venv/bin/python /tests/verify_mux_lib.py "$@"
