#!/bin/bash
if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set."
    exit 1
fi

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

# Anti-memorization: deterministically perturb the committed data (a small seeded
# jitter of every tuning parameter, leaving the outcome and row count unchanged),
# then re-run the agent's /app/analysis.R, grading only what it reproduces on the
# perturbed data. A solution that genuinely fits the complementary log-log model
# tracks the change; one that hardcodes or recalls coefficients, deviances, tests,
# marginal effects, permutation quantities, or fitted probabilities no longer
# matches the re-estimate the verifier computes from the same perturbed file.
/opt/test-venv/bin/python3 /tests/generate_hidden_data.py

# Enforce the R entry point and regrade from scratch. A missing or non-R
# analysis.R leaves the outputs unwritten and every artifact test fails.
rm -rf /app/outputs
mkdir -p /app/outputs
Rscript /app/analysis.R || true

/opt/test-venv/bin/python3 -m pytest --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -v -rA
if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
