#!/bin/bash
# Compile every Scala source under /app/app/src/main/scala into the classes dir.
# Stdlib only: the classpath is just the Scala 3 runtime shipped with the
# distribution. No third party jars, no build tool, no network.
set -euo pipefail

APP=/app/app
OUT="$APP/build/classes"
SCALA_HOME="${SCALA_HOME:-/opt/scala3}"

mkdir -p "$OUT"
rm -rf "${OUT:?}/"*

mapfile -t SOURCES < <(find "$APP/src/main/scala" -name '*.scala' | sort)
if [ "${#SOURCES[@]}" -eq 0 ]; then
    echo "no Scala sources found under $APP/src/main/scala" >&2
    exit 1
fi

"$SCALA_HOME/bin/scalac" -d "$OUT" "${SOURCES[@]}"
echo "compiled ${#SOURCES[@]} source file(s) -> $OUT"
