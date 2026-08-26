"""CLI entrypoint for the gaa-extract syscall trace guard.

test.sh uses this wrapper (via verifier-support/build_guard.sh) to run the
Cargo build under strace so that neither a build script nor any generated code
can open the reference tests in /tests or the oracle tree in /solution. It
exits with the wrapped command's return code, or a non-zero guard code if the
traced process opened a protected path.

Usage:
    trace_run.py [--policy tests|model-fit] [--cwd DIR] -- CMD [ARGS...]
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tracing import MODEL_FIT_POLICY, TESTS_POLICY, TraceViolation, run_traced

GUARD_BLOCKED = 97
GUARD_UNAVAILABLE = 98


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", choices=["tests", "model-fit"], default="tests")
    parser.add_argument("--cwd", default=None)
    parser.add_argument("cmd", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    cmd = args.cmd
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    if not cmd:
        print("trace_run: no command provided", file=sys.stderr)
        return 2

    policy = MODEL_FIT_POLICY if args.policy == "model-fit" else TESTS_POLICY
    try:
        result = run_traced(cmd, policy=policy, cwd=args.cwd)
    except TraceViolation as exc:
        print(f"trace_run: BLOCKED - {exc}", file=sys.stderr)
        return GUARD_BLOCKED
    except RuntimeError as exc:
        print(f"trace_run: {exc}", file=sys.stderr)
        return GUARD_UNAVAILABLE

    if result.stdout:
        sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

