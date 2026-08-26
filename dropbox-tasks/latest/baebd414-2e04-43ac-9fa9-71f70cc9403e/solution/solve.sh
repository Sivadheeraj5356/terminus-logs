#!/bin/bash
set -euo pipefail

install -d -m 0755 /app/live/zones /app/live/keys /app/live/run /app/recovery
install -m 0640 /solution/files/harbor-ops.key /app/live/keys/harbor-ops.key
install -m 0644 /solution/files/named.conf /app/live/named.conf
install -m 0644 /solution/files/external.harbor.test.zone /app/live/zones/external.harbor.test.zone
install -m 0644 /solution/files/external.192.0.2.zone /app/live/zones/external.192.0.2.zone
install -m 0644 /solution/files/internal.harbor.test.zone /app/live/zones/internal.harbor.test.zone
install -m 0644 /solution/files/internal.192.0.2.zone /app/live/zones/internal.192.0.2.zone
install -m 0644 /solution/files/internal.rpz /app/live/zones/internal.rpz

find /app/evidence -maxdepth 1 -type f -print0 | sort -z | xargs -0 sha256sum > /app/recovery/evidence.sha256
install -m 0644 /solution/files/changes.tsv /app/recovery/changes.tsv
named-checkconf -z /app/live/named.conf
