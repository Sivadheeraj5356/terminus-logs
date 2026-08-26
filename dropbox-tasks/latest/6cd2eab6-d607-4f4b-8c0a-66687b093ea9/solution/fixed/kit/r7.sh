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
export TARGET_ROUTE

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

IFS=$'\n' FILES=($(printf '%s\n' "${FILES[@]}" | LC_ALL=C sort -u))
IFS=$'\n' FORBIDDEN=($(printf '%s\n' "${FORBIDDEN[@]}" | LC_ALL=C sort -u))

REV_DIR="$MIRROR_ROOT/$REPO/fineweb-edu-score-2/revisions/$REVISION/files"
META_PATH="$MIRROR_ROOT/$REPO/fineweb-edu-score-2/revisions/$REVISION/metadata.json"
TRANSCRIPT_DIGEST=$(sha256sum "$TRANSCRIPT" | awk '{print $1}')
export META_PATH
META_DIGEST=$(PYTHONPATH=kit python3 -c "from n7 import metadata_digest; import os; print(metadata_digest(os.environ['META_PATH']))")
GRADLE_DIGEST=$(PYTHONPATH=kit python3 -c "from n7 import gradle_lock_digest; print(gradle_lock_digest())")

FILE_JSON=""
for rel in "${FILES[@]}"; do
  for bad in "${FORBIDDEN[@]}"; do
    [[ "$rel" == "$bad" ]] && echo "forbidden file in route: $rel" >&2 && exit 2
  done
  full="$REV_DIR/$rel"
  [[ -f "$full" ]] || { echo "missing file $full" >&2; exit 2; }
  digest=$(bash kit/h2.sh "$full")
  bytes=$(wc -c <"$full" | tr -d ' ')
  FILE_JSON+='{"path":"'"$rel"'","sha256":"'"$digest"'","bytes":'"$bytes"'},'
done
FILE_JSON="${FILE_JSON%,}"

TMP_LOCK="$(mktemp "${LOCK_OUT}.XXXXXX")"
cleanup_tmp() { rm -f "$TMP_LOCK"; }
trap cleanup_tmp EXIT

python3 - <<PY >"$TMP_LOCK"
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
print(json.dumps(lock, indent=2, sort_keys=True))
PY

mv -f "$TMP_LOCK" "$LOCK_OUT"
trap - EXIT
