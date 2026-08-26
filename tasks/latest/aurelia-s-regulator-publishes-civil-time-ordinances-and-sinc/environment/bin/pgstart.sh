#!/bin/sh
# Starts the local PostgreSQL cluster if it is not already accepting connections.
set -e
pg_isready -h 127.0.0.1 -q && exit 0
pg_ctlcluster 15 main start
for _ in $(seq 30); do
    pg_isready -h 127.0.0.1 -q && exit 0
    sleep 0.3
done
echo "postgres did not come up" >&2
exit 1
