#!/bin/bash
set -euo pipefail
cd /app
rm -rf /app/build
cmake -S /app -B /app/build -DCMAKE_BUILD_TYPE=Release
cmake --build /app/build --target caption-beam --parallel 1
