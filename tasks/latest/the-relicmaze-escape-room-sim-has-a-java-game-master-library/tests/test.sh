#!/bin/bash
# RelicMaze verifier entry point. Verifier dependencies (Node.js, PostgreSQL
# client, Python/pytest, JDBC driver) are baked into environment/Dockerfile.

mkdir -p /logs/verifier

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set."
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

# Bring PostgreSQL online and reset it to the authoritative dataset so the
# scored run is deterministic regardless of anything the agent did to the DB.
/usr/local/bin/relicmaze-ensure-db.sh
psql -h localhost -U relickeeper -d relicmaze -v ON_ERROR_STOP=1 -f /tests/db/seed.sql >/dev/null 2>&1

# Run the scenario suite via pytest (which drives the npm/Node verifier).
python3 -m pytest -o cache_dir=/tmp/pytest_cache \
    --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA
RC=$?
if [ "$RC" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
