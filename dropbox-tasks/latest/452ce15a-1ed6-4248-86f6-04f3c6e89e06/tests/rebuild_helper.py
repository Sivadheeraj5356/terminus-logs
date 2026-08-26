"""Rebuild piezo-audit from /app/environment for grading."""

import subprocess
from pathlib import Path

BIN = Path("/app/environment/bin/piezo-audit")


def rebuild() -> None:
    subprocess.run(
        ["bash", "/app/environment/scripts/build.sh"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if not BIN.is_file():
        raise RuntimeError(f"missing rebuilt binary: {BIN}")
