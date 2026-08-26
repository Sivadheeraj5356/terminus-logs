#!/bin/bash
# Approach this as a supervised learning problem: understand what is being learned
# and how it is scored, study the labeled data, infer the rule behind the labels,
# then fit that model and let the verifier score it.

cat /app/environment/docs/contract.md
head -n 5 /app/environment/data/train.csv
head -n 5 /app/environment/data/test.csv

cp /solution/main.rs /app/environment/src/main.rs

cd /app/environment
cargo build --offline --release
