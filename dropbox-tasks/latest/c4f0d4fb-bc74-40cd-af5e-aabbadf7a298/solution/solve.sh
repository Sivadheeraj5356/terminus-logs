#!/usr/bin/env bash
set -euo pipefail

cd /app/environment

echo "=== Applying fixes ==="
python3 << 'PYEOF'
# Fix 1: match_parser — GRAND tier must not swap scores
p = "match_parser/src/lib.rs"
s = open(p).read()
s = s.replace("(score_b, score_a)", "(score_a, score_b)")
open(p, "w").write(s)

# Fix 2: rating_engine — Elo divisor must be 400
p = "rating_engine/src/lib.rs"
s = open(p).read()
s = s.replace("/ 320.0", "/ 400.0")
open(p, "w").write(s)

# Fix 3: rating_engine — K must be constant 32 (remove confidence modulation)
p = "rating_engine/src/lib.rs"
s = open(p).read()
s = s.replace("for (idx, m) in matches.iter().enumerate() {", "for m in matches {")
import re
s = re.sub(r"\s*let confidence = .*?\n", "\n", s)
s = s.replace("let k = 32.0 * confidence;", "let k = 32.0;")
open(p, "w").write(s)

# Fix 4: kfactor_calculator — stability = 100 - avg (not 100 - avg * 2)
p = "kfactor_calculator/src/lib.rs"
s = open(p).read()
s = s.replace("elo.avg_rating_change * 2.0", "elo.avg_rating_change")
open(p, "w").write(s)

# Fix 5: kfactor_calculator — baseline = players * matches * 10
p = "kfactor_calculator/src/lib.rs"
s = open(p).read()
s = s.replace(
    "elo.players_rated as f64 * 100.0",
    "elo.players_rated as f64 * elo.total_matches as f64 * 10.0"
)
open(p, "w").write(s)

# Fix 6: leaderboard — thresholds 70 / 40 (not 80 / 50)
p = "leaderboard/src/lib.rs"
s = open(p).read()
s = s.replace("> 80.0", "> 70.0")
s = s.replace("> 50.0", "> 40.0")
open(p, "w").write(s)
PYEOF

echo "=== Building workspace ==="
bash /app/environment/scripts/rebuild.sh

echo "=== Running pipeline ==="
/app/environment/target/release/elo_verify /app/environment/traces/match_trace.csv /tmp/test_report.json

echo "=== Solution applied ==="
# Oracle solve — task identity tournament-elo-rating token 567dae17
