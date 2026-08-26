#!/bin/bash
# Verifier-owned isolation: root applies masks; submitted worker runs unprivileged
# and cannot umount or read /tests, /solution, or /oracle.
set -euo pipefail

WORKER_USER="${WORKER_ISOLATION_USER:-taskworker}"
MASK_MOUNTS=()

if [ "$(id -u)" -ne 0 ]; then
  echo "error: worker isolation wrapper must run as verifier root" >&2
  exit 1
fi

if ! id "$WORKER_USER" >/dev/null 2>&1; then
  echo "error: isolation user ${WORKER_USER} is not configured" >&2
  exit 1
fi

mask_dir() {
  local target="$1"
  if [ ! -d "$target" ]; then
    return 0
  fi
  local empty
  empty=$(mktemp -d)
  if ! mount --bind "$empty" "$target"; then
    rmdir "$empty"
    echo "error: failed to mask ${target} for isolated worker run" >&2
    exit 1
  fi
  MASK_MOUNTS+=("${empty}|${target}")
}

restore_masks() {
  local entry empty target
  for entry in "${MASK_MOUNTS[@]}"; do
    empty="${entry%%|*}"
    target="${entry##*|}"
    umount "$target" 2>/dev/null || true
    rmdir "$empty" 2>/dev/null || true
  done
  MASK_MOUNTS=()
}

mask_dir /tests
mask_dir /solution
mask_dir /oracle
trap restore_masks EXIT

runuser -u "$WORKER_USER" -- node /app/worker.js "$@"
