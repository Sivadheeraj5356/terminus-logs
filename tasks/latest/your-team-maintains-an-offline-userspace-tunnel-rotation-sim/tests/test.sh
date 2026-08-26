#!/bin/bash

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile."
    exit 1
fi

# Keep ablation fixtures and verifier sources out of reach of /app/bin/wg_run.
# Pytest (root) retains access; the driver runs as user wgdriver.
mkdir -p /opt/tb_verifier
if [ -d /tests/stock_broken ]; then
  rm -rf /opt/tb_verifier/stock_broken
  cp -a /tests/stock_broken /opt/tb_verifier/stock_broken
  rm -rf /tests/stock_broken
fi
chown -R root:root /opt/tb_verifier /tests
chmod -R go-rwx /opt/tb_verifier
chmod 700 /tests
# Ensure driver-writable runtime paths exist with correct ownership.
mkdir -p /app/output/run_traces /app/state/wg \
  /app/environment/w8g/staged /app/environment/w8g/durable
chown -R wgdriver:wgdriver /app/output /app/state /app/environment/w8g

# Don't change anything below this line except the test file path or pytest flags.
pytest --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA

# Produce reward file (REQUIRED)
if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
