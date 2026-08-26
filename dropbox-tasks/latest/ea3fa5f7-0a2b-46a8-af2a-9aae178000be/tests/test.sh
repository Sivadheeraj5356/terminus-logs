#!/bin/bash
set -uo pipefail

export PATH="/opt/verifier-scripts:/usr/sbin:/sbin:/opt/verifier-venv/bin:${PATH}"

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
printf '%s\n' '{"version":"1.0.0","results":{"tool":{"name":"pytest"},"summary":{"tests":0,"passed":0,"failed":0,"skipped":0},"tests":[]}}' > /logs/verifier/ctrf.json

if [ "$PWD" = "/" ]; then
 echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile before running this script."
 echo 0 > /logs/verifier/reward.txt
 exit 1
fi

# Rebuild under /app, then leave candidate-writable /app before pytest so an
# injected /app/pytest.py cannot shadow the verifier package during collection.
cd /app || {
 echo 0 > /logs/verifier/reward.txt
 exit 1
}

if [ -f /app/Makefile ]; then
 rebuild-habitat-resupply || {
  echo 0 > /logs/verifier/reward.txt
  exit 1
 }
fi

TEST_DIR="${TEST_DIR:-/tests}"
ISOLATE="${TEST_DIR}/verifier_isolate_run.sh"
chmod +x "${ISOLATE}" || {
 echo 0 > /logs/verifier/reward.txt
 exit 1
}

if [ -d "${TEST_DIR}/verifier-fixtures" ]; then
 mkdir -p /opt/verifier-fixtures
 cp -a "${TEST_DIR}/verifier-fixtures/." /opt/verifier-fixtures/
 chmod -R 700 /opt/verifier-fixtures
fi

# Tests + oracle stay readable by root/pytest only; candidate CLIs run as nobody.
chmod -R go-rwx "${TEST_DIR}" 2>/dev/null || true
if [ -d /solution ]; then
 chmod -R go-rwx /solution 2>/dev/null || true
fi

if ! command -v runuser >/dev/null 2>&1; then
 for candidate in /usr/sbin/runuser /sbin/runuser; do
  if [ -x "$candidate" ]; then
   PATH="$(dirname "$candidate"):${PATH}"
   export PATH
   break
  fi
 done
fi
if runuser -u nobody -- test -r "${TEST_DIR}/test_outputs.py" 2>/dev/null; then
 echo "ERROR: /tests still readable by nobody after lockdown" >&2
 echo 0 > /logs/verifier/reward.txt
 exit 1
fi

mkdir -p /tmp/verifier-pytest
cd /tmp/verifier-pytest || {
 echo 0 > /logs/verifier/reward.txt
 exit 1
}

# Pytest (root) imports helpers from TEST_DIR only — never from candidate /app.
export PYTHONPATH="${TEST_DIR}"
unset PYTEST_ADDOPTS || true

set +e
/opt/verifier-venv/bin/python -m pytest -rA -o cache_dir=/tmp/pytest_cache \
 --ctrf /logs/verifier/ctrf.json "${TEST_DIR}/test_outputs.py"
rc=$?
if [ "$rc" -eq 0 ]; then
 echo 1 > /logs/verifier/reward.txt
else
 echo 0 > /logs/verifier/reward.txt
fi
