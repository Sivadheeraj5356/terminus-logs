#!/bin/bash
set -euo pipefail

bash /app/scripts/start_mysql.sh

cd /app
mix helix.lock
