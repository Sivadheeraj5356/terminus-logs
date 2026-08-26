#!/bin/bash
# Offline task (task.toml [environment] allow_internet = false): pytest and
# pytest-json-ctrf are pinned in environment/verifier-requirements.txt and installed
# in environment/Dockerfile at image build time. Do not pip install or use the network here.

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile."
    exit 1
fi

python3 -m pytest --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA

# Produce reward file (REQUIRED)
if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
