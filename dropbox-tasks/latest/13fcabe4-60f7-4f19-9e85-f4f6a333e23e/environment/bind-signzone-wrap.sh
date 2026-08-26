#!/bin/bash
# dnssec-signzone initializes libuv netmgr and fails when Harbor sandboxes leak fds.
set -euo pipefail

real="/usr/bin/dnssec-signzone.real"
if [[ ! -x "${real}" ]]; then
  echo "dnssec-signzone: missing ${real}" >&2
  exit 127
fi

if [[ -d /proc/self/fd ]]; then
  while IFS= read -r fd; do
    [[ "${fd}" =~ ^[0-9]+$ ]] || continue
    if (( fd > 2 )); then
      exec {fd}<&- 2>/dev/null || true
    fi
  done < <(ls -1 /proc/self/fd 2>/dev/null | sort -n)
fi

ulimit -n 65536 2>/dev/null || ulimit -n 4096 2>/dev/null || ulimit -n 2048 2>/dev/null || true

if command -v prlimit >/dev/null 2>&1; then
  exec prlimit --nofile=65536:65536 -- "${real}" "$@"
fi
exec "${real}" "$@"
