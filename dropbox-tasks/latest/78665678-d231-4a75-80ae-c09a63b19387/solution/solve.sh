#!/usr/bin/env bash
set -euo pipefail
SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TASK_DIR="${TASK_DIR:-/app/task_file}"
cd "$TASK_DIR"
INPUT_DIR="$TASK_DIR/input_data"
OUTPUT_DIR="$TASK_DIR/output_data"
SOURCE_DIR="$TASK_DIR/src"
SOURCE_FILE="$SOURCE_DIR/main.c"
BINARY="$TASK_DIR/opt"

for required in "$INPUT_DIR/config.txt" "$INPUT_DIR/panels.tsv" "$INPUT_DIR/samples.tsv"; do
  if [ ! -s "$required" ]; then
    echo "missing pathogen batching input: $required" >&2
    exit 2
  fi
done

rm -f "$BINARY"
mkdir -p "$OUTPUT_DIR" "$SOURCE_DIR"
cp "$SCRIPT_ROOT/src/main.c" "$SOURCE_FILE"
gcc -O2 -std=c11 -Wall -Wextra -Werror "$SOURCE_FILE" -o "$BINARY"
"$BINARY" "$INPUT_DIR" "$OUTPUT_DIR"
test -s "$OUTPUT_DIR/batches.json"
