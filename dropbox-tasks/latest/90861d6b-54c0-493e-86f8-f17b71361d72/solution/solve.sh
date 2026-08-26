#!/bin/bash
set -euo pipefail
root="$(cd "$(dirname "$0")" && pwd)"
install -m 0644 "$root/reference/Model.java" /app/environment/model/Model.java
install -m 0644 "$root/reference/Main.java" /app/environment/cli/Main.java
install -m 0644 "$root/reference/Recovery.java" /app/environment/ingest/Recovery.java
install -m 0644 "$root/reference/Dynamics.java" /app/environment/analysis/Dynamics.java
install -m 0644 "$root/reference/StateStore.java" /app/environment/storage/StateStore.java
install -m 0644 "$root/reference/DatabaseLoader.java" /app/environment/storage/DatabaseLoader.java
install -m 0644 "$root/reference/ResultWriter.java" /app/environment/format/ResultWriter.java
/app/environment/build.sh
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
/app/environment/run.sh analyze \
  --spec /app/environment/fixtures/brownian.def \
  --state "$work/experiment.state" \
  --db "$work/experiment.duckdb" \
  --report "$work/experiment.json" > "$work/stdout.json"
cmp "$work/experiment.json" "$work/stdout.json"
/app/environment/run.sh rebuild \
  --state "$work/experiment.state" \
  --db "$work/rebuilt.duckdb" \
  --report "$work/rebuilt.json" > "$work/rebuilt-stdout.json"
cmp "$work/experiment.json" "$work/rebuilt.json"
cmp "$work/rebuilt.json" "$work/rebuilt-stdout.json"
