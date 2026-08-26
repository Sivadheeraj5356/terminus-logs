"""Verifier helpers for GMP lot-release integrity attestation checks."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

APP = Path("/app")
TRACE_DIR = APP / "state" / "verifier-traces"
ENTRY = APP / "bin" / "gmp-lot-integrity-attestor"


def attestation_entry() -> Path:
    """Resolve the documented integrity attestation entry path."""
    override = os.environ.get("BATCH_RELEASE_BIN")
    if override:
        return Path(override)
    return ENTRY


def assert_no_tests_access(trace_file: Path) -> None:
    """Ensure attestation did not inspect mounted verifier files."""
    trace = trace_file.read_text(errors="replace")
    bad = [line for line in trace.splitlines() if '"/tests' in line]
    assert not bad, "attestation accessed verifier files under /tests:\n" + "\n".join(bad[:10])


def traced_exec(args: list[str], env: dict | None = None) -> Any:
    """Run an issuance mode under file-access tracing."""
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    trace_file = TRACE_DIR / f"trace-{len(list(TRACE_DIR.glob('trace-*.log')))}.log"
    launch = [str(attestation_entry()), *args]
    proc = subprocess.run(
        [
            "strace",
            "-f",
            "-e",
            "trace=%file",
            "-o",
            str(trace_file),
            *launch,
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert trace_file.is_file(), "strace did not write a file-access trace"
    assert_no_tests_access(trace_file)
    return proc


def census(metadata: Path, env: dict | None = None) -> Any:
    return traced_exec(["census", "--metadata", str(metadata)], env=env)


def attest_release(metadata: Path, stage: Path, report: Path, env: dict | None = None) -> Any:
    return traced_exec(
        [
            "attest-release",
            "--metadata",
            str(metadata),
            "--stage",
            str(stage),
            "--output",
            str(report),
        ],
        env=env,
    )
