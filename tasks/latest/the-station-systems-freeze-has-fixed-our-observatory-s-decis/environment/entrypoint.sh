#!/bin/bash
set -euo pipefail

pg_ctlcluster 16 main start

for _ in $(seq 1 120); do
    if (echo > /dev/tcp/127.0.0.1/5432) 2>/dev/null; then
        break
    fi
    sleep 0.5
done

exec "$@"
