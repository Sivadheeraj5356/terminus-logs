#!/bin/bash

mkdir -p /logs/verifier
# Write a default reward of 0 immediately, before any setup work runs.
# If any of the setup steps (cp, cd, ln, etc.) exits early, the reward
# file is still present so the platform can pick up a well-formed 0.
# Successful test runs overwrite this at the end.
echo 0 > /logs/verifier/reward.txt

if [ "$PWD" = "/" ]; then
  echo "Error: No working directory set."
  exit 0
fi

# Set up the npm test workspace (the underlying vitest + playwright suites
# still run via `npm run test` / `npm run test:e2e` from inside pytest).
rm -rf /tmp/ui-task-tests
cp -R /tests /tmp/ui-task-tests
cd /tmp/ui-task-tests
ln -s /opt/ui-task-tests/node_modules node_modules
export PATH="/opt/ui-task-tests/node_modules/.bin:$PATH"

# Invoke the Python pytest suite, which shells out to the underlying JS suites.
python3 -m pytest /tests/test_outputs.py -rA
rc=$?
if [ "$rc" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
