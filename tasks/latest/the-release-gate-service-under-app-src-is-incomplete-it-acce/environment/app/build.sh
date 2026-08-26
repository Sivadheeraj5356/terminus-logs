#!/bin/bash
# Compile the gate service and rebuild the H2 approvals database from the
# seed SQL. Runs offline; every dep is baked into /opt/jars/ by the image
# build. Called from run_gate.sh and by the oracle at solve time.
set -euo pipefail

APP=/app
SRC="$APP/src"
BIN="$APP/bin"
DATA="$APP/data"
JARS=/opt/jars
CLASSPATH="$JARS/h2.jar:$JARS/snakeyaml.jar"

mkdir -p "$BIN" "$APP/build"

# 1. Compile Java sources into a classes tree, then jar them.
CLASSES="$APP/build/classes"
rm -rf "$CLASSES"
mkdir -p "$CLASSES"

javac -encoding UTF-8 -d "$CLASSES" -cp "$CLASSPATH" $(find "$SRC" -name '*.java' | sort)

# 2. Emit a fat-ish runtime jar containing only our own classes; jars in
#    CLASSPATH are loaded from /opt/jars/ at runtime.
(cd "$CLASSES" && jar --create --file "$BIN/gate.jar" --main-class=gate.Main .)

# 3. Rebuild the H2 approvals database from the seed. Deterministic: same
#    SQL always yields byte-identical output for the RunScript trace.
rm -f "$DATA/approvals.mv.db" "$DATA/approvals.trace.db"
java -cp "$JARS/h2.jar" org.h2.tools.RunScript \
    -url "jdbc:h2:file:$DATA/approvals" \
    -user sa \
    -script "$DATA/seed_approvals.sql"

echo "[build] gate.jar built; approvals.mv.db seeded"
