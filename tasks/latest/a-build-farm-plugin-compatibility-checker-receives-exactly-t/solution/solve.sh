#!/bin/bash
set -euo pipefail
cd /app
cp /solution/Selgate.kt /app/Selgate.kt
kotlinc /app/Selgate.kt -include-runtime -d /app/selgate.jar
