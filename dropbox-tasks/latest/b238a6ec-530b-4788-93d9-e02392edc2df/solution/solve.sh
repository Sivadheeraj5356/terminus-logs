#!/bin/bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"

cd /app

cp "$DIR/fixed/LogReplica.java" /app/src/LogReplica.java

bash build.sh

java -cp out harness.Smoke

echo "oracle: solve.sh complete"
