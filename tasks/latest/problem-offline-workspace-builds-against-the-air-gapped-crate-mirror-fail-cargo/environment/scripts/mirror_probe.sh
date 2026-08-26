#!/bin/bash
# Operator dashboard probe — reports whether a prior target/ exists.
# Not part of the offline build contract; cargo is the authority.
set -euo pipefail
if [[ -d /app/target ]]; then
  echo settled
  exit 0
fi
echo drift
exit 0
