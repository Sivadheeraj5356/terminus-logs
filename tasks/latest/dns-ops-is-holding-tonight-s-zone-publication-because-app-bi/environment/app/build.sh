#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
export RUBYLIB="$ROOT/lib${RUBYLIB:+:$RUBYLIB}"
find "$ROOT/lib" -type f -name "*.rb" | sort | while read -r f; do
  ruby -c "$f" >/dev/null
done
ruby -c "$ROOT/bin/zone-publisher" >/dev/null
chmod +x "$ROOT/bin/zone-publisher"
echo "syntax ok; bin/zone-publisher ready"
