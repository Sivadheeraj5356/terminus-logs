#!/bin/bash
# Start the local PostgreSQL cluster (idempotent) and wait until it accepts
# connections. Safe to call repeatedly.
set -uo pipefail

PG_VER="$(ls /etc/postgresql 2>/dev/null | head -n1)"
if [ -z "${PG_VER:-}" ]; then
    echo "no postgresql cluster found" >&2
    exit 1
fi

pg_ctlcluster "$PG_VER" main start >/dev/null 2>&1 || true

for _ in $(seq 1 60); do
    if pg_isready -q -h localhost -p 5432; then
        exit 0
    fi
    sleep 0.5
done

echo "postgres did not become ready" >&2
exit 1
