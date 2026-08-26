#!/bin/bash
set -uo pipefail

# Verifier dependencies are installed in environment/Dockerfile.
# Add task-specific verifier-only Python packages there, not here.

mkdir -p /logs/verifier

# Check if we're in a valid working directory
if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile before running this script."
    echo 0 > /logs/verifier/reward.txt
    exit 0
fi

VERIFIER_CONFIG_ROOT="/logs/verifier/active"
mkdir -p "$VERIFIER_CONFIG_ROOT"
cp /tests/data/readiness_contract.json "$VERIFIER_CONFIG_ROOT/readiness_contract.json"
cp /tests/data/readiness_rules.json "$VERIFIER_CONFIG_ROOT/readiness_rules.json"
cp /tests/data/mlflow_manifest.json "$VERIFIER_CONFIG_ROOT/mlflow_manifest.json"
cp /tests/data/weights.json "$VERIFIER_CONFIG_ROOT/weights.json"
chmod -R a-w "$VERIFIER_CONFIG_ROOT"
chmod a+r "$VERIFIER_CONFIG_ROOT"/*.json

export READINESS_CONTRACT_PATH="$VERIFIER_CONFIG_ROOT/readiness_contract.json"
export READINESS_RULES_PATH="$VERIFIER_CONFIG_ROOT/readiness_rules.json"
export MLFLOW_MANIFEST_PATH="$VERIFIER_CONFIG_ROOT/mlflow_manifest.json"
export MODEL_WEIGHTS_PATH="$VERIFIER_CONFIG_ROOT/weights.json"

pkill -9 -f "mlflow server" 2>/dev/null || true
if [ -f /tmp/mlflow.pid ]; then
  kill -9 "$(cat /tmp/mlflow.pid)" 2>/dev/null || true
fi
rm -f /tmp/mlflow.pid /tmp/mlflow.log
sleep 2

rm -rf /app/output /app/queue/done /app/mlflow_tracking /app/mlflow_artifacts
mkdir -p /app/output /app/queue/done /app/mlflow_tracking /app/mlflow_artifacts
chown -R taskworker:taskworker /app/output /app/queue /app/mlflow_tracking /app/mlflow_artifacts

mkdir -p /app/queue/pending/.seed
cp /tests/data/pending/*.json /app/queue/pending/.seed/
rm -f /app/queue/pending/*.json
cp /app/queue/pending/.seed/*.json /app/queue/pending/
chown -R taskworker:taskworker /app/queue

PYTHONPATH=/tests python3 - <<'PY'
from static_integrity import verify_static_inputs_match_trusted

verify_static_inputs_match_trusted()
PY

export MLFLOW_FORCE_RESTART=1
bash /tests/start_mlflow.sh

for _ in $(seq 1 60); do
  if python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=1)" 2>/dev/null; then
    break
  fi
  sleep 0.5
done

sleep 2

python3 - <<PY
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

manifest = json.load(open(os.environ["MLFLOW_MANIFEST_PATH"]))
name = manifest["experiment_name"]
base = "http://127.0.0.1:5000/api/2.0/mlflow"

for _ in range(12):
    lookup = (
        f"{base}/experiments/get-by-name?"
        f"experiment_name={urllib.parse.quote(name)}"
    )
    try:
        with urllib.request.urlopen(lookup, timeout=5) as resp:
            if resp.status == 200:
                raise SystemExit(0)
    except urllib.error.HTTPError as err:
        if err.code not in (404, 500):
            raise
    except urllib.error.URLError:
        time.sleep(0.5)
        continue

    create_req = urllib.request.Request(
        f"{base}/experiments/create",
        data=json.dumps({"name": name}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(create_req, timeout=5)
        raise SystemExit(0)
    except urllib.error.HTTPError as err:
        if err.code in (200, 409):
            raise SystemExit(0)
    time.sleep(0.5)

raise SystemExit("MLflow experiment warmup failed")
PY

bash /tests/run_worker_isolated.sh

python -m pytest -o cache_dir=/tmp/pytest_cache \
  --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA
status=$?

if [ "$status" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
