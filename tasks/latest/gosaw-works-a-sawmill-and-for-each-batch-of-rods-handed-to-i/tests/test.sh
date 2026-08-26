#!/bin/bash
set -uo pipefail

# Artifacts are created up front so that no path through this script can leave
# /logs/verifier without a reward.txt or a ctrf.json. reward.txt starts at 0 and
# is only raised to 1 on a full pass.
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
if [ ! -s /logs/verifier/ctrf.json ]; then
  cat > /logs/verifier/ctrf.json <<'JSON'
{"results":{"tool":{"name":"pytest"},"summary":{"tests":0,"passed":0,"failed":0,"pending":0,"skipped":0,"other":0,"start":0,"stop":0},"tests":[]}}
JSON
fi

if [ "$PWD" = "/" ]; then
  echo "refusing to run from /" >&2
  echo 0 > /logs/verifier/reward.txt
  exit 1
fi

TEST_DIR="${TEST_DIR:-/tests}"

cd /app || { echo 0 > /logs/verifier/reward.txt; echo "cannot enter /app"; exit 1; }

# Compile the submitted sources so the engine under test is the one on disk. A
# build that does not go through stops here with a clean zero.
rm -rf /tmp/sawsplitclasses
javac -d /tmp/sawsplitclasses /app/Main.java /app/Sawmill.java || {
  echo 0 > /logs/verifier/reward.txt
  echo "build failed"
  exit 1
}
chmod -R 755 /tmp/sawsplitclasses

# Isolation. The engine under test is started as an unprivileged user (see the
# runner in test_outputs.py), and the suite's own files belong to root alone, so
# the engine cannot open them however it spells the path. There is nothing to
# delegate to and the batches have to be settled by the engine itself.
chown -R root:root "${TEST_DIR}" 2>/dev/null || true
chmod -R go-rwx "${TEST_DIR}" 2>/dev/null || true
chmod 700 "${TEST_DIR}" 2>/dev/null || true
chown -R root:root /solution 2>/dev/null || true
chmod 700 /solution 2>/dev/null || true

python3 -m pytest --ctrf /logs/verifier/ctrf.json "${TEST_DIR}/test_outputs.py" -v -rA -p no:cacheprovider

if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
