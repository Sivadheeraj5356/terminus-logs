"""Copy task trees for isolated pytest runs."""

from __future__ import annotations

import shutil
from pathlib import Path


def copy_task(src: Path, tmp: Path | None = None) -> Path:
    """Copy a task fixture tree into a fresh directory."""
    dest = tmp or Path("/tmp") / f"tray_copy_{src.name}"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    return dest
