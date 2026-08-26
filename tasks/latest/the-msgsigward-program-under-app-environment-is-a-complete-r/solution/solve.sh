#!/bin/bash
set -euo pipefail

cd /app/environment

# Audit result: for each planted defect in internal/msgsig/verify.go, a witness
# request bundle on which the shipped verifier's decision is insecure.
cp /solution/findings.json /app/environment/findings.json

echo "oracle: solve.sh complete"
