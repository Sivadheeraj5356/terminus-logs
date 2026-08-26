#!/bin/bash
self="${BASH_SOURCE[0]}"
if grep -q $'\r' "$self" 2>/dev/null; then
  tmp="${TMPDIR:-/tmp}/solve-$$.sh"
  tr -d '\r' < "$self" > "$tmp"
  chmod +x "$tmp"
  exec bash "$tmp" "$@"
fi
set -euo pipefail
export GOROOT="${GOROOT:-/usr/local/go}"
export PATH="${GOROOT}/bin:/usr/local/go/bin:${PATH}"

SRC=""
for candidate in "/solution/files" "/oracle/solution/files" "/task/solution/files"; do
  if [ -f "${candidate}/internal/chartwalk/walk.go" ]; then
    SRC="${candidate}"
    break
  fi
done
if [ -z "${SRC}" ]; then
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
  if [ -f "${script_dir}/files/internal/chartwalk/walk.go" ]; then
    SRC="${script_dir}/files"
  fi
fi
if [ -z "${SRC}" ]; then
  echo "oracle: solution files not found" >&2
  exit 1
fi

cd /app
cp -R "${SRC}/internal/"* /app/internal/
go build -mod=readonly -o /app/bin/helmvals ./cmd/helmvals
test -x /app/bin/helmvals
