#!/bin/bash
set -euo pipefail

# Install the reference resolver over the starter, then build it the same way the
# runtime shim does.
cp /solution/Main.java /app/Main.java
cd /app
javac -d /app/classes /app/Main.java
