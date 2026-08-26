#!/usr/bin/env bash
set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$SRC_DIR/policy_auditor.c" /app/policy_auditor.c
gcc -O2 -std=c11 -Wall -Wextra -o /usr/local/bin/policy-auditor /app/policy_auditor.c
/usr/local/bin/policy-auditor /app/task_file/input_data/repo /app/task_file/output_data/findings.sarif
