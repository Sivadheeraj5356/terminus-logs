#!/bin/bash
# Compiles the sources under /app/src into the native executable /app/bin/folding.
set -euo pipefail

mkdir -p /app/bin
mlton -output /app/bin/folding /app/src/folding.mlb
