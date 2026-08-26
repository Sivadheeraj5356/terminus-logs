#!/usr/bin/env bash
set -uo pipefail

export PATH="/usr/local/go/bin:/app/bin:/opt/verifier-venv/bin:${PATH}"

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
echo '{"version":"1.0.0","results":{"tool":{"name":"pytest"},"summary":{"tests":0,"passed":0,"failed":0,"skipped":0},"tests":[]}}' > /logs/verifier/ctrf.json

cd /app || {
  echo 0 > /logs/verifier/reward.txt
  exit 1
}

TEST_DIR="${TEST_DIR:-/tests}"

/app/scripts/build.sh || {
  echo 0 > /logs/verifier/reward.txt
  exit 1
}

# Private verifier copy is root-only. Product binary runs as BOILOFF_RUN_USER and
# cannot read this tree; pytest (root) still can.
PRIV="/opt/verifier-private"
rm -rf "${PRIV}"
mkdir -p "${PRIV}"
cp -a "${TEST_DIR}/." "${PRIV}/"
chown -R root:root "${PRIV}"
chmod -R go-rwx "${PRIV}"
chmod 700 "${PRIV}"
# Best-effort lock on the mounted /tests tree when writable.
if touch "${TEST_DIR}/.boiloff_write_probe" 2>/dev/null; then
  rm -f "${TEST_DIR}/.boiloff_write_probe"
  chown -R root:root "${TEST_DIR}" 2>/dev/null || true
  chmod -R go-rwx "${TEST_DIR}" 2>/dev/null || true
  chmod 700 "${TEST_DIR}" 2>/dev/null || true
fi
chmod -R go-rwx /opt/verifier-venv 2>/dev/null || true

set +e
/opt/verifier-venv/bin/python -m pytest -o cache_dir=/tmp/pytest_cache --ctrf /logs/verifier/ctrf.json "${PRIV}/test_outputs.py" -rA
if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
