"""Pytest fixtures for waxlane-allot verifier probes."""

from __future__ import annotations

import subprocess
from pathlib import Path


def pytest_configure() -> None:
    """Install verify-time court probes into /opt/verifier-fixtures (not in agent image)."""
    script = Path(__file__).resolve().parent / "install_waxlane_probes.sh"
    src = Path(__file__).resolve().parent / "probe-court"
    if script.is_file() and src.is_dir():
        subprocess.run(["bash", str(script), str(src)], check=False)
