#!/bin/bash
set -euo pipefail

cd /app
# --forward skips already-applied hunks, making this safe to rerun
patch -p1 --forward < /solution/fix.patch
