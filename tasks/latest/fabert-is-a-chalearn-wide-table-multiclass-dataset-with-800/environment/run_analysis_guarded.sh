#!/bin/bash
set -euo pipefail

ANALYSIS_R="${ANALYSIS_R:-/app/analysis.R}"
TRACE_LOG="$(mktemp /tmp/fabert-analysis-trace.XXXXXX.log)"
trap 'rm -f "$TRACE_LOG"' EXIT

set +e
strace -f -qq -s 4096 \
  -e trace=open,openat,openat2,stat,statx,access,faccessat,faccessat2,readlink,readlinkat,execve,execveat \
  -o "$TRACE_LOG" \
  Rscript "$ANALYSIS_R"
rc=$?
set -e

python3 - "$TRACE_LOG" <<'PY'
import os
import re
import sys
from pathlib import Path

trace_path = Path(sys.argv[1])
forbidden = []
python_execs = []
quote_re = re.compile(r'"((?:[^"\\]|\\.)*)"')

def unescape(value):
    return bytes(value, "utf-8").decode("unicode_escape")

def normalize(raw):
    if not raw or raw.startswith("<"):
        return []
    candidates = []
    value = raw
    if not value.startswith("/"):
        value = "/app/" + value
    norm = os.path.normpath(value)
    candidates.append(norm)
    if norm.startswith("/proc/self/root/"):
        candidates.append(os.path.normpath(norm[len("/proc/self/root") :]))
    try:
        candidates.append(os.path.realpath(norm))
    except OSError:
        pass
    return candidates

for line in trace_path.read_text(errors="ignore").splitlines():
    syscall = line.split("(", 1)[0].split()[-1]
    paths = [unescape(match.group(1)) for match in quote_re.finditer(line)]
    if syscall in {"execve", "execveat"} and paths:
        executable = os.path.basename(paths[0])
        if executable.startswith("python"):
            python_execs.append(paths[0])
    if syscall in {
        "open",
        "openat",
        "openat2",
        "stat",
        "statx",
        "access",
        "faccessat",
        "faccessat2",
        "readlink",
        "readlinkat",
    }:
        for raw in paths:
            for candidate in normalize(raw):
                if candidate == "/tests" or candidate.startswith("/tests/"):
                    forbidden.append(raw)

if forbidden or python_execs:
    if forbidden:
        print("Forbidden verifier path read detected:", sorted(set(forbidden))[:5], file=sys.stderr)
    if python_execs:
        print("Forbidden Python child process detected:", sorted(set(python_execs))[:5], file=sys.stderr)
    sys.exit(97)
PY
guard_rc=$?

if [ "$rc" -ne 0 ]; then
  exit "$rc"
fi
exit "$guard_rc"
