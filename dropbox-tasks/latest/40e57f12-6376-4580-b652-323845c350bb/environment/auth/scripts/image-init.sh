#!/bin/bash
set -euo pipefail

mkdir -p /app/auth/data /app/auth/out
go run /app/auth/tools/genkeys.go /app/auth/keys
/app/auth/bin/build.sh
