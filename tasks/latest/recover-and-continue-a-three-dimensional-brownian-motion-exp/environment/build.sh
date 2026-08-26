#!/bin/bash
set -euo pipefail
root="$(cd "$(dirname "$0")" && pwd)"
rm -rf "$root/build"
mkdir -p "$root/build/classes"
mapfile -t sources < <(find "$root/cli" "$root/model" "$root/format" "$root/ingest" "$root/analysis" "$root/storage" -name '*.java' -type f | sort)
if [ "${#sources[@]}" -eq 0 ]; then echo "no Java sources" >&2; exit 1; fi
javac --release 17 -cp /app/lib/duckdb_jdbc.jar -d "$root/build/classes" "${sources[@]}"
jar --create --file "$root/build/diffusion-analyzer.jar" --main-class org.terminus.calc.Main -C "$root/build/classes" .
