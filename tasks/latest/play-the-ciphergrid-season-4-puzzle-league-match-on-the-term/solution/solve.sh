#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd /app

mkdir -p /app/var /app/bin /app/app/src
chmod 0777 /app/bin /app/var 2>/dev/null || true
chmod -R a+rwX /app/app /app/var /app/bin 2>/dev/null || true

for f in combostreak rivalry echoedge; do
  rm -f "/app/app/src/${f}.zig"
  install -m 0666 "$SCRIPT_DIR/fixed/${f}.zig" "/app/app/src/${f}.zig"
done

rm -f /app/var/match_chain_tip.txt

bash /app/build.sh
test -x /app/bin/cipherleague

OUT=/app/var/oracle_report.json
/app/bin/cipherleague score --archive /app/data/season4 --out "$OUT"
grep -q season_score_digest "$OUT"
grep -q playtest_seal "$OUT"
grep -q rivalry_digest "$OUT"
grep -q match_crown "$OUT"
