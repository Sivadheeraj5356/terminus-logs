#!/usr/bin/env bash
# Milestone 1 oracle: implement the version total order and the manifest parser.
# Installs the worked Version.scala and ManifestParser.scala over the stubs, then
# cold rebuilds the CLI.
set -euo pipefail

SRC=/app/app/src/main/scala/modverse
ORACLE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cp "$ORACLE/Version.scala" "$SRC/Version.scala"
cp "$ORACLE/ManifestParser.scala" "$SRC/ManifestParser.scala"

bash /app/app/build.sh
