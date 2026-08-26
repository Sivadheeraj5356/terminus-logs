#!/bin/bash

# Verifier dependencies (pytest, pytest-json-ctrf, redis-py, redis-server, node)
# are all baked into environment/Dockerfile. Nothing is installed or downloaded
# here, so this runs with no network access.

mkdir -p /logs/verifier

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile before running this script."
    exit 1
fi

# Bring the dispatch stack up using the task's configuration. Both starts are
# tolerant of an instance the agent may have already left running.
redis-server /app/config/redis.conf >/tmp/redis-boot.log 2>&1 || true
node /app/src/server.js >/tmp/dispatch-server.log 2>&1 &

python3 -m pytest -o cache_dir=/tmp/pytest_cache \
  --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA
RC=$?
if [ "$RC" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
