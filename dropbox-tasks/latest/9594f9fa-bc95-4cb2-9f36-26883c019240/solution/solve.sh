#!/bin/bash
set -euo pipefail

cd /app
cp /solution/admission_rules.adb /app/src/admission_rules.adb
make -C /app
