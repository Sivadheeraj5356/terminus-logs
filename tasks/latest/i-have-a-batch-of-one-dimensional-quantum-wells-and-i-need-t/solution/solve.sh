#!/bin/bash
set -euo pipefail

# Resolve this script's own directory so solve.dart is found next to it.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Deliver the Dart solver where the task expects it, then run it on the batch.
cp "$SCRIPT_DIR/solve.dart" /app/solve.dart
dart /app/solve.dart /app/data/potentials.json /app/energies.json
