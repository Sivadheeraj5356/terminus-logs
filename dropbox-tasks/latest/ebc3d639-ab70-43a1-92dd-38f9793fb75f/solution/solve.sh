#!/bin/bash
set -euo pipefail
cp /solution/solution.R /app/solution.R
Rscript /app/solution.R /app/data /app/design_output.csv
