#!/bin/bash
set -euo pipefail
cp /solution/analysis.R /app/analysis.R
rm -rf /app/outputs
mkdir -p /app/outputs
Rscript /app/analysis.R

test -f /app/outputs/metrics.json
test -f /app/outputs/predictions.csv
test -f /app/outputs/class_report.csv
test -f /app/outputs/confusion_matrix.csv
test -f /app/outputs/missing_report.csv
test -f /app/outputs/validation_report.csv
test -f /app/outputs/stability_refit_predictions.csv
test -f /app/outputs/stability_refit_report.csv
test -f /app/outputs/robust_lambda_consensus_report.csv
test -f /app/outputs/feature_drop_refit_report.csv
test -f /app/outputs/protein_pair_drop_refit_report.csv
test -f /app/outputs/boundary_refit_report.csv
test -f /app/outputs/paired_boundary_reselection_report.csv
test -f /app/outputs/model_manifest.json
