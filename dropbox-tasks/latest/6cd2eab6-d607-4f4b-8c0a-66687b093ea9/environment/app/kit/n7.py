"""Shared digest helpers for asset-lock generation and validation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def canonical_sha256(payload: dict) -> str:
    """Return a stable digest for JSON metadata payloads."""
    text = json.dumps(payload, indent=2, sort_keys=True)
    return hashlib.sha256(text.encode()).hexdigest()


def metadata_digest(path: str | Path) -> str:
    """Digest mirror metadata.json using the lock contract."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return canonical_sha256(data)


def gradle_lock_digest(root: str | Path = "/app/gradle/dependency-locks") -> str:
    """Digest Gradle lockfiles in lexicographic order."""
    root_path = Path(root)
    if not root_path.is_dir():
        return hashlib.sha256(b"").hexdigest()
    names = sorted(p.name for p in root_path.iterdir() if p.suffix == ".lockfile")
    joined = ",".join(names)
    return hashlib.sha256(joined.encode()).hexdigest()
