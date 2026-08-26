#!/usr/bin/env bash
# Raise NOFILE before BIND signing tools run (Daytona/Harbor sandboxes).
set -euo pipefail

ulimit -n 65536 2>/dev/null || ulimit -n 4096 2>/dev/null || ulimit -n 2048 2>/dev/null || true

if command -v prlimit >/dev/null 2>&1; then
  prlimit --nofile=65536:65536 --pid="$$" 2>/dev/null || true
fi

if [[ -d /proc/self/fd ]]; then
  while IFS= read -r fd; do
    [[ "${fd}" =~ ^[0-9]+$ ]] || continue
    if (( fd > 2 )); then
      exec {fd}<&- 2>/dev/null || true
    fi
  done < <(ls -1 /proc/self/fd 2>/dev/null | sort -n)
fi
