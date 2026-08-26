#!/bin/bash
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
# Verifier isolation: the reference warden is mounted at /solution during
# grading. Remove it before the candidate jar is built or run so no candidate
# code can read or execute the oracle (solve.sh) to fabricate the report.
# By the oracle's own run this has already been applied to /app/src, so this
# only ever strips the mount, never the graded sources.
rm -rf /solution 2>/dev/null || true
if [ -e /solution/solve.sh ]; then
    echo "Error: reference solution still reachable at /solution; refusing to grade."
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi
if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile before running this script."
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi
cd /app
find src -name "*.java" > sources.list
javac -d /app/build @sources.list
jar --create --file /app/bin/spoolward.jar --main-class=com.spoolward.Main -C /app/build .
cd /tests
python3 -I -m pytest -c /dev/null --rootdir=/tests --confcutdir=/tests \
  -o cache_dir=/tmp/pytest_cache \
  --ctrf /logs/verifier/ctrf.json /tests/test_report.py -rA
if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
