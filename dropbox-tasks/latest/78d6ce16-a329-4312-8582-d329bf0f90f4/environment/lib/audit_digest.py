"""Audit digest helpers for batch reconciliation inputs."""

from __future__ import annotations

import hashlib
from pathlib import Path


def file_sha256(path: Path) -> str:
    """Return the SHA-256 digest for an input file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()
