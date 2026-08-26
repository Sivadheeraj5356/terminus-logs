#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
install -m 0755 "$SCRIPT_DIR/p/wf" /app/p/wf
install -m 0755 "$SCRIPT_DIR/p/lib/shared_paths.sh" /app/p/lib/shared_paths.sh
install -m 0755 "$SCRIPT_DIR/p/lib/clf_fit.sh" /app/p/lib/clf_fit.sh
install -m 0755 "$SCRIPT_DIR/p/lib/score_run.sh" /app/p/lib/score_run.sh

rm -rf /app/artifacts
/app/p/wf train --data /app/data/training.parquet --artifacts-dir /app/artifacts

python /app/scripts/stop_django.py >/dev/null 2>&1 || true
cd /app/django_api
python manage.py migrate --noinput >/dev/null
python manage.py seed_records >/dev/null
python manage.py runserver 127.0.0.1:8000 --noreload >/tmp/oracle-django.log 2>&1 &
server_pid=$!
cleanup() {
  kill "$server_pid" >/dev/null 2>&1 || true
  wait "$server_pid" >/dev/null 2>&1 || true
}
trap cleanup EXIT

python - <<'PY'
import time
import requests

for _ in range(60):
    try:
        response = requests.get("http://127.0.0.1:8000/api/v1/health/", timeout=1)
        if response.status_code == 200:
            break
    except requests.RequestException:
        pass
    time.sleep(1)
else:
    raise SystemExit("oracle API did not become ready")
PY

completed=0
for attempt in 1 2; do
  if /app/p/wf run-drift --batch-id batch-stable \
      --api-url http://127.0.0.1:8000/api/v1 \
      --data /app/data/training.parquet \
      --artifacts-dir /app/artifacts; then
    completed=1
    break
  fi
  sleep "$attempt"
done
[[ "$completed" -eq 1 ]]
