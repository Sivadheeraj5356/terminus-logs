#!/usr/bin/env bash
# Milestone 4 oracle: add lang gated pruning of the walk and the loaded manifest
# set output. Installs the milestone 4 Resolver.scala over the milestone 3 one,
# then cold rebuilds.
set -euo pipefail

SRC=/app/app/src/main/scala/modverse
ORACLE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cp "$ORACLE/Resolver.scala" "$SRC/Resolver.scala"

bash /app/app/build.sh
