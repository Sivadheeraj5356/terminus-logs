#!/bin/bash
set -euo pipefail

cd /solution
bash patches/apply_n1.sh
bash patches/apply_n2.sh
bash patches/apply_n3.sh
bash patches/apply_n4.sh
bash patches/apply_n5.sh

test -f /app/environment/r05/source/n5.cpp
mkdir -p /app/output
