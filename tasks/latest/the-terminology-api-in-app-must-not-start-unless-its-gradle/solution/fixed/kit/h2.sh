#!/usr/bin/env bash
set -euo pipefail
target="$1"
sha256sum -- "$target" | awk '{print $1}'
