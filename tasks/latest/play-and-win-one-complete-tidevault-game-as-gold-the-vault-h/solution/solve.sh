#!/usr/bin/env bash
set -euo pipefail

/usr/bin/python3 /solution/oracle_player.py \
    --model /solution/strong.tvnn \
    --model-id tidevault-linear-s20260720-e0001 \
    --model-sha256 588cc9dd43cac20ebf622d3547f4e677e187d66cb4138be1dcea43090773931e \
    --node-budget 12000 \
    --width 16 \
    --max-depth 18 \
    --seed 2026072002 \
    --arena-timeout 30
