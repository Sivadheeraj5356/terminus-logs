#!/bin/bash
cp /solution/solution.R /app/estimate.R
Rscript /app/estimate.R /app/data /app/results.csv
test -s /app/results.csv
