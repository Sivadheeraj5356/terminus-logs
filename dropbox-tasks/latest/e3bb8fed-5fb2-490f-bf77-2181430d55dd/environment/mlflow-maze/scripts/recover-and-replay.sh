#!/bin/bash
set -euo pipefail

ROOT=/app/mlflow-maze
if [ "$#" -eq 0 ]; then
    TRACKING="$ROOT/fixtures/tracking.sqlite"
    BOARD="$ROOT/config/maze.yaml"
    PUZZLES="$ROOT/config/puzzles.toml"
    OUTPUT="$ROOT/out/level-manifest.json"
elif [ "$#" -eq 4 ]; then
    TRACKING=$1
    BOARD=$2
    PUZZLES=$3
    OUTPUT=$4
else
    echo "usage: recover-and-replay.sh [TRACKING_DB MAZE_YAML PUZZLES_TOML OUTPUT]" >&2
    exit 2
fi

mkdir -p "$(dirname "$OUTPUT")"
"$ROOT/bin/maze-recover" recover \
    --tracking-db "$TRACKING" \
    --maze-yaml "$BOARD" \
    --puzzles-toml "$PUZZLES" \
    --output "$OUTPUT"
python3 "$ROOT/tools/validate_manifest.py" \
    "$ROOT/schema/level-manifest.schema.json" "$OUTPUT"
"$ROOT/bin/maze-recover" replay --manifest "$OUTPUT"
