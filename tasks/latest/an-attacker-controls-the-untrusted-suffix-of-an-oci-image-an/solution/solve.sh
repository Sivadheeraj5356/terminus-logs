#!/bin/sh
set -eu
install -m 0644 /solution/layer_gate.c /app/layer_gate.c
mkdir -p /app/output
gcc -std=c11 -O2 -Wall -Wextra -Werror /app/layer_gate.c -o /app/layer-gate
/app/layer-gate /app/evidence/extraction.policy /app/evidence/layers.manifest /app/output/extraction-security.json
