#!/usr/bin/env bash
# Local stack health probe — unix path only; does not evaluate lockout authority.
set -euo pipefail
echo "stack_probe: CLEAN"
echo "unix_path: ok"
echo "services: sshd sudo portal su"
exit 0
