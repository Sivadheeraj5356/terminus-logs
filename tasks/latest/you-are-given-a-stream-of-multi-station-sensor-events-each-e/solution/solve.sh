#!/usr/bin/env bash
set -euo pipefail
cp /solution/Main.java /app/Main.java
cd /app
javac -d /app/out /app/Main.java
