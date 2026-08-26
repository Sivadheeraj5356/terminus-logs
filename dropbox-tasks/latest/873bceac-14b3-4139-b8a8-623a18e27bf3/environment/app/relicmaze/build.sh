#!/bin/bash
# Compile the RelicMaze Java library. Output classes land in build/.
set -euo pipefail
cd "$(dirname "$0")"

CP="lib/postgresql.jar:lib/json.jar"
rm -rf build
mkdir -p build
javac -cp "$CP" -d build $(find src/main/java -name '*.java')
echo "compiled -> build/"
