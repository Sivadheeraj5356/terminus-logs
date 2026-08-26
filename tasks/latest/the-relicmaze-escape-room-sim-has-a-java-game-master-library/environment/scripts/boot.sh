#!/bin/bash
# Container entrypoint: bring PostgreSQL online, then hand off to the command.
set -uo pipefail

/usr/local/bin/relicmaze-ensure-db.sh || true

if [ "$#" -eq 0 ]; then
    exec sleep infinity
fi
exec "$@"
