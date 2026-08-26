#!/usr/bin/env Rscript
# Publish purchase probabilities for every unscored peak-season session.
# Read /app/environment/data/online_shoppers.csv (blank target = row to score),
# write /app/environment/outputs/predictions.csv (row_id, pred_proba)
# and metrics.json per /app/environment/contracts/output_contract.md.
# Run: Rscript /app/environment/analysis.R
