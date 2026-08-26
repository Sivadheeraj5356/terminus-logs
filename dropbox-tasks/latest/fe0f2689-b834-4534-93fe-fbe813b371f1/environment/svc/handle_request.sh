#!/usr/bin/env bash
set -euo pipefail

GRAPH_PATH="${CHAMBER_GRAPH_PATH:?}"
ENDPOINT="${CHAMBER_ENDPOINT:-/v1/topology}"

read -r request_line || true
# Drain headers.
while IFS= read -r line; do
  line="${line%$'\r'}"
  [ -z "$line" ] && break
done

method="${request_line%% *}"
rest="${request_line#* }"
path="${rest%% *}"
path="${path%%\?*}"

respond() {
  local status="$1"
  local body="$2"
  local reason="$3"
  printf 'HTTP/1.1 %s %s\r\n' "$status" "$reason"
  printf 'Content-Type: application/json\r\n'
  printf 'Content-Length: %s\r\n' "${#body}"
  printf 'Connection: close\r\n'
  printf '\r\n'
  printf '%s' "$body"
}

if [ "$method" != "GET" ]; then
  respond 405 '{"error":"method"}' "Method Not Allowed"
  exit 0
fi

case "$path" in
  /v1/health)
    respond 200 '{"ok":true}' "OK"
    ;;
  "$ENDPOINT")
    body="$(cat "$GRAPH_PATH")"
    respond 200 "$body" "OK"
    ;;
  /v1/topology)
    body="$(cat "$GRAPH_PATH")"
    respond 200 "$body" "OK"
    ;;
  *)
    respond 404 '{"error":"missing"}' "Not Found"
    ;;
esac
