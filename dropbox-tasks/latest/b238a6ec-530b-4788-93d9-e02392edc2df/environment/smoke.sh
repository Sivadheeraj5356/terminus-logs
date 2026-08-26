#!/bin/bash
set -e
cd /app
bash build.sh
java -cp out harness.Smoke
