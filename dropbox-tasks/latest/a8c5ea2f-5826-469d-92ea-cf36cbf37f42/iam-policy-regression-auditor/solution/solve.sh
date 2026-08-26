#!/bin/bash
set -euo pipefail

mkdir -p /app/task_file/output /tmp/policy-regression
cp /solution/analyzer.rs /app/task_file/output/policy_regression_analyzer.rs
rustc --edition 2021 -C opt-level=3 /app/task_file/output/policy_regression_analyzer.rs -o /tmp/policy-regression/analyzer
/tmp/policy-regression/analyzer /app/task_file/policy_case.txt /app/task_file/output/policy_regression_report.json
