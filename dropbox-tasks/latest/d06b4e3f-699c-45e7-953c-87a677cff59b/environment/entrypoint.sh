#!/bin/bash
set -e

/usr/local/bin/mockkms >/var/log/mockkms.log 2>&1 &
echo $! > /var/run/mockkms.pid

for _ in $(seq 1 50); do
    if curl -s -o /dev/null http://127.0.0.1:8500/healthz; then
        break
    fi
    sleep 0.1
done

exec "$@"
