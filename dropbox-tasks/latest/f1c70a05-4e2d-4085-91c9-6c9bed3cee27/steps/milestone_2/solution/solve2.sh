#!/usr/bin/env bash
# Milestone 2 oracle: implement the build list selection rule and the lazy
# transitive walk. Installs the worked Resolver.scala over the stub, then cold
# rebuilds. The version order and manifest parser from milestone 1 are already in
# place.
set -euo pipefail

SRC=/app/app/src/main/scala/modverse
ORACLE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cp "$ORACLE/Resolver.scala" "$SRC/Resolver.scala"

bash /app/app/build.sh
