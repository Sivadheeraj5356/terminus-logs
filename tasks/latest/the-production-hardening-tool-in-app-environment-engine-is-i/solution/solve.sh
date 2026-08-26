#!/bin/bash
set -euo pipefail

node /solution/apply_solution.js
node /app/environment/engine/cli/harden.js \
  /app/environment/engine \
  /app/environment/dossier/incident-dossier.md \
  /app/environment/fixtures \
  /app/out
