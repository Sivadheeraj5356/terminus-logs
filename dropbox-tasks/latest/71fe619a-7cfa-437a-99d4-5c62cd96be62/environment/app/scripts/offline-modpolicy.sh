#!/usr/bin/env bash
set -euo pipefail

MIRROR="/app/var/module-mirror"
DB="/app/var/policy-index/policy.db"
BIN="/app/bin/modpolicylock"
REQUEST=""
GOOS="linux"
GOARCH="amd64"
LOCK="/output/modpolicy.lock.json"
REPORT="/output/policy-report.json"
ROOT="/app"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --request) REQUEST="$2"; shift 2 ;;
    --goos) GOOS="$2"; shift 2 ;;
    --goarch) GOARCH="$2"; shift 2 ;;
    --lock) LOCK="$2"; shift 2 ;;
    --report) REPORT="$2"; shift 2 ;;
    --root) ROOT="$2"; shift 2 ;;
    --db) DB="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$REQUEST" ]]; then
  echo "missing --request" >&2
  exit 2
fi

export MODPOLICY_OFFLINE=1 GOPROXY=off GOSUMDB=off

# Prefer a DB under the active root when resolving from a copied tree.
ROOT_DB="$ROOT/var/policy-index/policy.db"
if [[ "$ROOT" != "/app" && "$DB" == "/app/var/policy-index/policy.db" ]]; then
  DB="$ROOT_DB"
fi

mkdir -p "$(dirname "$DB")" "$(dirname "$LOCK")"

need_reindex=1
if [[ -f "$DB" ]]; then
  complete=$(sqlite3 "$DB" "SELECT index_complete FROM index_meta WHERE id=1;" 2>/dev/null || echo "")
  pin_count=$(sqlite3 "$DB" "SELECT COUNT(*) FROM pins;" 2>/dev/null || echo "0")
  expected=$(grep -cve '^\s*$' "$MIRROR/policy/pins.jsonl" || echo "0")
  if [[ "$complete" == "1" && "$pin_count" == "$expected" ]]; then
    need_reindex=0
  fi
fi

if [[ "$need_reindex" == "1" ]]; then
  rm -f "$DB"
  "$BIN" reindex --mirror "$MIRROR" --db "$DB"
fi

set +e
"$BIN" resolve \
  --request "$REQUEST" \
  --goos "$GOOS" --goarch "$GOARCH" \
  --lock "$LOCK" --db "$DB" --root "$ROOT"
rc=$?
set -e
if [[ "$rc" -ne 0 ]]; then
  exit "$rc"
fi

set +e
"$BIN" report \
  --request "$REQUEST" \
  --goos "$GOOS" --goarch "$GOARCH" \
  --report "$REPORT" --db "$DB" --root "$ROOT"
rc=$?
set -e
if [[ "$rc" -ne 0 ]]; then
  exit "$rc"
fi

if ! "$BIN" verify --lock "$LOCK" --report "$REPORT"; then
  exit 1
fi

if [[ -x /app/bin/modpolicy-inspect ]]; then
  /app/bin/modpolicy-inspect graph-compare --lock "$LOCK" --report "$REPORT"
fi

exit 0
