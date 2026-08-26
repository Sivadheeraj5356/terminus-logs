#!/bin/bash
set -uo pipefail

# Verifier setup needs root. Image must keep default USER root so Harbor runs this as root.
if [ "$(id -u)" -ne 0 ]; then
  echo "Error: tests/test.sh must run as root to lock protected mounts and grade."
  mkdir -p /logs/verifier
  echo 0 > /logs/verifier/reward.txt
  exit 0
fi

# Check if we're in a valid working directory
if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile before running this script."
    mkdir -p /logs/verifier
    echo 0 > /logs/verifier/reward.txt
    exit 0
fi

mkdir -p /logs/verifier /home/model/tmp /home/model/go/cache /home/model/grade_src

# Hide protected mounts from the model user before any submitted compile/run.
# /logs/verifier is a Harbor bind mount; chmod may be ignored on Docker Desktop,
# but we still best-effort lock it. /tests lock below is mandatory and reliable.
chown root:root /logs/verifier 2>/dev/null || true
chmod 700 /logs/verifier 2>/dev/null || true
find /logs/verifier -mindepth 1 -maxdepth 1 -exec chown root:root {} + 2>/dev/null || true
find /logs/verifier -type f -exec chmod 600 {} + 2>/dev/null || true
find /logs/verifier -type d -exec chmod 700 {} + 2>/dev/null || true

if [ -e /tests ]; then
  chown root:root /tests
  chmod 700 /tests
  if [ -w /tests ] || [ -r /tests ]; then
    find /tests -mindepth 1 -exec chown root:root {} + 2>/dev/null || true
    find /tests -type d -exec chmod 700 {} + 2>/dev/null || true
    find /tests -type f -exec chmod 600 {} + 2>/dev/null || true
  fi
fi

if [ -d /solution ]; then
  chown root:root /solution
  chmod 700 /solution
  find /solution -mindepth 1 -exec chown root:root {} + 2>/dev/null || true
  find /solution -type d -exec chmod 700 {} + 2>/dev/null || true
  find /solution -type f -exec chmod 600 {} + 2>/dev/null || true
fi

# Submitted code builds and runs as non-root; ensure /app and Go caches are writable by model.
chown model:model /app /home/model /home/model/go /home/model/tmp /home/model/go/cache /home/model/grade_src
find /app -mindepth 1 -exec chown model:model {} +
find /home/model/go /home/model/tmp /home/model/grade_src -exec chown model:model {} +
chmod 755 /app
chmod 755 /home/model /home/model/go /home/model/tmp /home/model/go/cache /home/model/grade_src

# Run tests as root (can read /tests); staged compile/run inside pytest uses user model.
python -m pytest --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA
if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
