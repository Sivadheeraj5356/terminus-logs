#!/bin/bash
set -euo pipefail

cd /app

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
oracle_source=""
for candidate in "$script_dir/recover.c" /oracle/recover.c /solution/recover.c; do
    if [ -f "$candidate" ]; then
        oracle_source="$candidate"
        break
    fi
done

if [ -z "$oracle_source" ]; then
    echo "oracle recover.c not found" >&2
    exit 1
fi

cp "$oracle_source" /app/src/recover.c
make clean all
mkdir -p /app/output
/app/bin/recover
