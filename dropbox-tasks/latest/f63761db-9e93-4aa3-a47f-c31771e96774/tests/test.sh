#!/usr/bin/env bash
set -uo pipefail

mkdir -p /logs/verifier

if [ "$PWD" = "/" ]; then
  echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile."
  echo 0 > /logs/verifier/reward.txt
  exit 0
fi

/usr/local/sbin/run-kirigami-verifier
rc=$?

if [ "$rc" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
