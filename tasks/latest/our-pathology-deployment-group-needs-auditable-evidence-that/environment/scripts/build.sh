#!/bin/bash
set -euo pipefail
cd /app
mvn -q -DskipTests package dependency:copy-dependencies -DincludeScope=runtime
test -s /app/target/djl-parity-trial-1.0.0.jar
test -d /app/target/dependency
