#!/usr/bin/env bash
set -euo pipefail
exec /app/environment/target/release/pathlab "$@"
