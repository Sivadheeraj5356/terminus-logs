#!/bin/bash
set -euo pipefail

# Oracle: build the histogram mode consolidation profiler from the normal
# source file shipped next to this script and expose it as /app/consolidate.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

mkdir -p /app/output /app/consolidate-src /app/consolidate-classes
cp "$SCRIPT_DIR/Main.java" /app/consolidate-src/Main.java

javac -d /app/consolidate-classes /app/consolidate-src/Main.java

cat > /app/consolidate <<'WRAP'
#!/bin/sh
exec java -cp /app/consolidate-classes Main "$@"
WRAP
chmod +x /app/consolidate

ls -l /app/consolidate
