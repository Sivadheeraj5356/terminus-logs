#!/bin/sh
set -eu
test -f /app/environment/adjudicator.py
exec python3 /app/environment/adjudicator.py --environment /app/environment --output /app/out
