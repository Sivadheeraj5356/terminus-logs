#!/usr/bin/env bash
set -euo pipefail

make -C /app clean >/dev/null 2>&1 || true
make -C /app
