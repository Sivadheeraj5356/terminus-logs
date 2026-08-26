#!/usr/bin/env bash
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
echo '{"version":"1.0.0","results":{"tool":{"name":"pytest"},"summary":{"tests":0,"passed":0,"failed":0,"skipped":0},"tests":[]}}' > /logs/verifier/ctrf.json
if [ "$PWD" = "/" ]; then
  echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile before running this script."
  exit 1
fi
export PATH="/usr/local/cargo/bin:/opt/verifier-venv/bin:/usr/local/bin:${PATH}"
export CARGO_NET_OFFLINE=true
# Candidate processes must not inherit a verifier PYTHONPATH.
unset PYTHONPATH
export PYTHONPATH=""

MOUNT_TESTS="${TEST_DIR:-/tests}"
WORK="/tmp/lda-verifier-tests"
PRIV="/opt/verifier-private"
rm -rf "${WORK}" "${PRIV}" /opt/verifier-fixtures/lda
cp -a "${MOUNT_TESTS}/." "${WORK}/"
mkdir -p "${PRIV}/golden_lib" "${PRIV}/broken_lib"
mv "${WORK}/reference_lda.py" "${PRIV}/reference_lda.py"
cp -a "${WORK}/golden_lib/." "${PRIV}/golden_lib/"
cp -a "${WORK}/broken_lib/." "${PRIV}/broken_lib/"
rm -rf "${WORK}/golden_lib" "${WORK}/broken_lib"
python3 "${WORK}/gen_hidden_fixture.py"

# Private reference + golden/broken libs: root-only (candidate ldactl runs as nobody).
chown -R root:root "${PRIV}" "${WORK}"
chmod -R go-rwx "${PRIV}" "${WORK}"
chmod -R a+rX /opt/verifier-fixtures/lda 2>/dev/null || true

mkdir -p /app/state /app/output
chown -R nobody:nogroup /app/state /app/output

cd /app || exit 1
bash /app/scripts/rebuild-ldactl.sh || exit 1

# Run pytest in isolated mode from a root-only work dir (not /app), so:
# - agent-written /app/pytest.py cannot hijack -m pytest
# - PYTHONPATH is ignored by -I; reference is loaded only via sys.path in tests
set +e
cd "${WORK}" || exit 1
/opt/verifier-venv/bin/python3 -I -m pytest \
  -o cache_dir=/tmp/pytest_cache \
  --ctrf /logs/verifier/ctrf.json \
  test_outputs.py -rA
if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
