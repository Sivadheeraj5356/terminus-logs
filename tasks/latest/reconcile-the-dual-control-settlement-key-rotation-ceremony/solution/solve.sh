#!/usr/bin/env bash
set -euo pipefail

mkdir -p /app/bin
install -m 700 /solution/rotate_token.py /app/bin/.rotate_token.py
install -m 755 /solution/rotate_ceremony.sh /app/bin/rotate_ceremony
/app/bin/rotate_ceremony
