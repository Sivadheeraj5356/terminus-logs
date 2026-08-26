#!/usr/bin/env bash
set -euo pipefail

# Deterministic partial-index fixture used by recovery drills.
MIRROR="/app/var/module-mirror"
DB="${1:-/app/var/policy-index/policy.db}"
PINS_FILE="$MIRROR/policy/pins.jsonl"

rm -f "$DB"
mkdir -p "$(dirname "$DB")"

sqlite3 "$DB" <<'SQL'
CREATE TABLE pins (
  path TEXT NOT NULL,
  version TEXT NOT NULL,
  goos TEXT NOT NULL,
  goarch TEXT NOT NULL,
  policy_revision TEXT NOT NULL,
  decision TEXT NOT NULL,
  PRIMARY KEY (path, goos, goarch, policy_revision)
);
CREATE TABLE decision_cache (
  path TEXT NOT NULL,
  version TEXT NOT NULL,
  goos TEXT NOT NULL,
  goarch TEXT NOT NULL,
  policy_revision TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  PRIMARY KEY (path, version, goos, goarch, policy_revision)
);
CREATE TABLE index_meta (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  policy_revision TEXT NOT NULL,
  index_complete INTEGER NOT NULL,
  write_epoch INTEGER NOT NULL
);
SQL

total=$(grep -cve '^\s*$' "$PINS_FILE" || true)
half=$(( total / 2 ))
if [[ "$half" -lt 1 ]]; then half=1; fi

# Advertise completeness early; only half of the pin rows are written below.
sqlite3 "$DB" "INSERT INTO index_meta(id,policy_revision,index_complete,write_epoch) VALUES(1,'rev20260717',1,$total);"

n=0
while IFS= read -r line; do
  [[ -z "${line// }" ]] && continue
  path=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["path"])' "$line")
  version=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["version"])' "$line")
  goos=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["goos"])' "$line")
  goarch=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["goarch"])' "$line")
  rev=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["policy_revision"])' "$line")
  decision=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["decision"])' "$line")
  sqlite3 "$DB" "INSERT INTO pins(path,version,goos,goarch,policy_revision,decision) VALUES('$path','$version','$goos','$goarch','$rev','$decision');"
  n=$((n+1))
  if [[ "$n" -ge "$half" ]]; then
    break
  fi
done < "$PINS_FILE"

echo "interrupt fixture: $n/$total pins, index_complete=1"
