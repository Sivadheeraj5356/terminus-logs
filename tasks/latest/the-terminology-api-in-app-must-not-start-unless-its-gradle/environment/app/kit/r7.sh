#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/app}"
MIRROR_ROOT="${HF_MIRROR_ROOT:-/data/hf-mirror}"
TRANSCRIPT="${HF_TRANSCRIPT:-/app/docs/release-council-transcript.md}"
LOCK_OUT="${HF_ASSET_LOCK:-/app/config/hf-assets.lock.json}"
TARGET_ROUTE="${TARGET_ROUTE:-public-synonym}"
REPO="HuggingFaceFW/fineweb-edu-score-2"
SCHEMA_VERSION="1.0.0"

cd "$APP_ROOT"
export TARGET_ROUTE APP_ROOT MIRROR_ROOT TRANSCRIPT LOCK_OUT

mapfile -t RULE_LINES < <(gawk -f kit/p9.awk "$TRANSCRIPT")
REVISION=""
declare -a FILES=()
declare -a FORBIDDEN=()
for line in "${RULE_LINES[@]}"; do
  key="${line%%=*}"
  val="${line#*=}"
  case "$key" in
    revision) REVISION="$val" ;;
    file) FILES+=("$val") ;;
    forbidden) FORBIDDEN+=("$val") ;;
  esac
done

if [[ -z "$REVISION" ]]; then
  REVISION="6f4a9e2c0b7d1a8f9c3e1d5b2a7c0e4d9f8b6a1c"
fi

REV_DIR="$MIRROR_ROOT/$REPO/fineweb-edu-score-2/revisions/$REVISION/files"
META_PATH="$MIRROR_ROOT/$REPO/fineweb-edu-score-2/revisions/$REVISION/metadata.json"
export META_PATH
TRANSCRIPT_DIGEST=$(sha256sum "$TRANSCRIPT" | awk '{print $1}')
META_DIGEST=$(PYTHONPATH=kit python3 -c "from n7 import metadata_digest; import os; print(metadata_digest(os.environ['META_PATH']))")
GRADLE_DIGEST=$(PYTHONPATH=kit python3 -c "from n7 import gradle_lock_digest; print(gradle_lock_digest())")

FILE_JSON=""
for rel in "${FILES[@]}"; do
  full="$REV_DIR/$rel"
  digest=$(bash kit/h2.sh "$full")
  bytes=$(wc -c <"$full" | tr -d ' ')
  FILE_JSON+='{"path":"'"$rel"'","sha256":"'"$digest"'","bytes":'"$bytes"'},'
done
FILE_JSON="${FILE_JSON%,}"

python3 - <<PY >"$LOCK_OUT"
import json
lock = {
  "lock_schema_version": "$SCHEMA_VERSION",
  "repository": "$REPO",
  "revision": "$REVISION",
  "source_metadata_digest": "$META_DIGEST",
  "transcript_digest": "$TRANSCRIPT_DIGEST",
  "gradle_lock_digest": "$GRADLE_DIGEST",
  "routes": [{
    "route_id": "$TARGET_ROUTE",
    "files": [${FILE_JSON}]
  }],
}
print(json.dumps(lock, indent=2))
PY
