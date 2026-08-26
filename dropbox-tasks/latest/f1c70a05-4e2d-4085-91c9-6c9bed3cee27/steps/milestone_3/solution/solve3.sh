#!/usr/bin/env bash
# Milestone 3 oracle: add main module replace and exclude authority while keeping
# dependency level replace and exclude inert. Installs the milestone 3
# Resolver.scala over the milestone 2 one, then cold rebuilds.
set -euo pipefail

SRC=/app/app/src/main/scala/modverse
ORACLE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cp "$ORACLE/Resolver.scala" "$SRC/Resolver.scala"

bash /app/app/build.sh
