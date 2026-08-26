#!/usr/bin/env bash
set -euo pipefail

ENV_ROOT="${ENV_ROOT:-/app/environment}"
OUTPUT_ROOT="${OUTPUT_ROOT:-/app/output}"
export ENV_ROOT OUTPUT_ROOT

mkdir -p "$OUTPUT_ROOT" "$OUTPUT_ROOT/rendered"
