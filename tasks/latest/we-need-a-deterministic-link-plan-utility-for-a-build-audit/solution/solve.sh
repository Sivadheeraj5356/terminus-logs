#!/bin/bash
set -euo pipefail

# Replace the intentionally incomplete starter with the full generalized linker,
# then rebuild it through the same project script used by the verifier.
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
install -m 0644 "$script_dir/main.go" /app/src/main.go
/app/build.sh
