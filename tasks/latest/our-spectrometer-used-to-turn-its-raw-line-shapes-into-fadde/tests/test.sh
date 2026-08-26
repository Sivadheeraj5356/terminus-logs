#!/bin/bash
set -uo pipefail

# Verifier dependencies are installed in environment/Dockerfile.
# Add task-specific verifier-only Python packages there, not here.

mkdir -p /logs/verifier

# Run pytest isolated from whatever the agent left in the work tree:
# PYTHONSAFEPATH keeps the current directory off sys.path, running from /tmp
# keeps the rootdir out of /app, and importlib import mode avoids inserting
# test/rootdir paths. Together these stop a stray file the agent may have left
# in /app from shadowing a standard-library import.
#
# Pin the config file, rootdir, and confcutdir to /tests. The agent runs as root
# and could plant files at / to make pytest exit 0 before grading anything:
#   - a /conftest.py that calls os._exit(0) during collection;
#   - a /pytest.ini that forces rootdir=/ or injects addopts = --collect-only.
# pytest derives rootdir from the common ancestor of the cwd, the test path, and
# the search that the --ctrf /logs argument drags up to /, so discovery would
# otherwise reach those planted files. sys.path hardening (PYTHONSAFEPATH,
# importlib mode) does not cover config or conftest loading. Passing -c with an
# explicit ini skips config discovery entirely, and --confcutdir=/tests stops the
# upward conftest search, so only the real checks under /tests can decide reward.
export PYTHONSAFEPATH=1
cd /tmp

# Produce the reward file (REQUIRED) - Harbor reads this, not the exit code.
python -m pytest -c /tests/pytest.ini \
  --rootdir=/tests --confcutdir=/tests \
  -o cache_dir=/tmp/pytest_cache -p no:cacheprovider \
  --import-mode=importlib \
  --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA
rc=$?
if [ "$rc" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
