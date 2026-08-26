#!/bin/bash
mkdir -p /logs/verifier && echo 0 > /logs/verifier/reward.txt

# Snapshot the API access log before the verifier's own services and queries
# add lines to it. The live-API test reads this snapshot.
cp /var/log/linkreg-api/access.log /logs/verifier/access-snapshot.log 2>/dev/null \
    || touch /logs/verifier/access-snapshot.log

/app/scripts/start-services.sh >/dev/null 2>&1 || true

python -m pytest --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA
if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
