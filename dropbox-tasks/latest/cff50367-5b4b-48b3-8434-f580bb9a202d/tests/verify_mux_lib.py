#!/usr/bin/env python3
"""Verifier-owned build+run helper for mux audits and pulse probes.

Rebuilds from /app/environment and runs the binary in a mount namespace where
/tests and /solution are not visible, so submitted Go code cannot read the
Python expected-report logic or the oracle patches.

Isolation is mandatory: if user namespaces are unavailable, unshare is missing,
the isolation probe fails, or the isolated command exits non-zero, verification
fails. There is no non-isolated fallback that would re-expose /tests or
/solution to the rebuilt binary.
"""

import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

ENV_ROOT = Path("/app/environment")
_BINARY: Optional[Path] = None


def build_mux() -> Path:
    global _BINARY
    if _BINARY is not None and _BINARY.exists():
        return _BINARY
    stage = Path("/tmp/mux-verify-stage")
    stage.mkdir(parents=True, exist_ok=True)
    binary = stage / "mux"
    subprocess.run(
        ["go", "build", "-o", str(binary), "./cmd/mux"],
        cwd=ENV_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    _BINARY = binary
    return binary


def run_isolated(binary, args, empty_tests, empty_solution):
    """Run the binary inside a namespace that hides /tests and /solution.

    Harbor mounts /tests for grading but often omits /solution on agent trials.
    Create both mount points at verifier runtime (never in the Dockerfile) so the
    bind-mounts do not fail before the rebuilt binary is evaluated.

    Raises SystemExit when isolation cannot be established or the isolated
    command fails. Never falls back to an unisolated run.
    """
    Path("/tests").mkdir(parents=True, exist_ok=True)
    Path("/solution").mkdir(parents=True, exist_ok=True)
    probe = (
        "import os,sys;"
        "sys.exit(0 if not ("
        "os.path.exists('/tests/test_outputs.py') "
        "or os.path.exists('/tests/verify_mux_lib.py') "
        "or os.path.exists('/solution/solve.sh')"
        ") else 97)"
    )
    quoted = " ".join("'" + part.replace("'", "'\"'\"'") + "'" for part in args)
    script = (
        "set -euo pipefail\n"
        f"mount -o bind '{empty_tests}' /tests\n"
        f"mount -o bind '{empty_solution}' /solution\n"
        f"python3 -c \"{probe}\"\n"
        f"exec '{binary}' {quoted}\n"
    )
    try:
        probe_ns = subprocess.run(
            ["unshare", "-Urm", "true"],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        sys.stderr.write("isolation unavailable: unshare not found\n")
        raise SystemExit(1)
    if probe_ns.returncode != 0:
        sys.stderr.write(probe_ns.stderr)
        sys.stderr.write(probe_ns.stdout)
        sys.stderr.write("isolation unavailable: user namespace probe failed\n")
        raise SystemExit(1)
    try:
        completed = subprocess.run(
            ["unshare", "-Urm", "bash", "-c", script],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        sys.stderr.write("isolation unavailable: unshare not found\n")
        raise SystemExit(1)
    if completed.returncode != 0:
        sys.stderr.write(completed.stderr)
        sys.stderr.write(completed.stdout)
        if completed.returncode == 97:
            sys.stderr.write("isolation failed: /tests or /solution still visible\n")
        else:
            sys.stderr.write(
                f"isolated mux failed with exit {completed.returncode}\n"
            )
        raise SystemExit(completed.returncode)
    return True


def main(argv):
    if not argv:
        print("usage: verify_mux_lib.py <audit|pulse> ...", file=sys.stderr)
        return 2

    binary = build_mux()
    with tempfile.TemporaryDirectory(prefix="mux-verify.") as stage_name:
        stage = Path(stage_name)
        empty_tests = stage / "empty-tests"
        empty_solution = stage / "empty-solution"
        empty_tests.mkdir()
        empty_solution.mkdir()
        run_isolated(binary, argv, empty_tests, empty_solution)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
