#!/bin/bash
# Verifier entrypoint. All deps are baked into the image; runs network-off.
set -uo pipefail

rm -rf /app/out
mkdir -p /app/out /logs/verifier
echo 0 > /logs/verifier/reward.txt

if [ "$PWD" = "/" ]; then
  echo "Error: no working directory; set WORKDIR in the Dockerfile." >&2
  exit 1
fi

export PATH="/usr/local/go/bin:/go/bin:$PATH"

cd /app || exit 1

if ! go build -o /app/pso_cli /app/cmd/pso 2>&1; then
  echo "Build failed" >&2
  echo 0 > /logs/verifier/reward.txt
  exit 1
fi

for conf_name in rosenbrock sphere rastrigin bug1 bug2 bug3 trap1 trap2 trap3 trap4 trap5; do
  if [ -f "/app/data/config_${conf_name}.json" ]; then
    if ! /app/pso_cli -config "/app/data/config_${conf_name}.json" -output "/app/out/${conf_name}.json" 2>&1; then
      echo "Binary run failed for ${conf_name}" >&2
      echo 0 > /logs/verifier/reward.txt
      exit 1
    fi
  fi
done

python3 -m pytest -p no:cacheprovider \
  --ctrf /logs/verifier/ctrf.json \
  /tests/test_outputs.py -rA
PYTEST_EXIT=$?

(exit "$PYTEST_EXIT")
if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
