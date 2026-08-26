#!/usr/bin/env bash
set -euo pipefail
rm -f /app/state/lda-corpus-staging.json /app/state/lda-count-staging.json /app/output/lda-topic-rollup.json
mkdir -p /app/state /app/output
