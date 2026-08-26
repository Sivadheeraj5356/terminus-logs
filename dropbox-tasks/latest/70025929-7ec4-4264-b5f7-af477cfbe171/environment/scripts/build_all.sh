#!/usr/bin/env bash
set -euo pipefail

export PATH="/usr/local/go/bin:/usr/local/bin:${PATH}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

mkdir -p bin
go build -o bin/g7bridge ./g7/bridge
cp -f bin/g7bridge /usr/local/bin/g7bridge
chmod 755 /usr/local/bin/g7bridge

cd x7/m2/k81
npm run build
