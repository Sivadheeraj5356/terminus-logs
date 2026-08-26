"""Shared digest helpers for asset-lock generation and validation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def canonical_sha256(payload: dict) -> str:
    """Return a stable digest for JSON metadata payloads."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def metadata_digest(path: str | Path) -> str:
    """Digest mirror metadata.json using the lock contract."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return canonical_sha256(data)


def gradle_lock_digest(root: str | Path = "/app/gradle/dependency-locks") -> str:
    """Digest Gradle lockfiles in lexicographic order."""
    root_path = Path(root)
    parts: list[bytes] = []
    for path in sorted(root_path.glob("*.lockfile")):
        data = path.read_bytes().replace(b"\r\n", b"\n")
        parts.append(path.name.encode() + b"\0" + data)
    return hashlib.sha256(b"".join(parts)).hexdigest()
