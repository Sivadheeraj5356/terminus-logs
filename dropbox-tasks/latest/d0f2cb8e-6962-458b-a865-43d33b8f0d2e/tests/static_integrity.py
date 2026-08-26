"""Verifier-owned snapshots of static worker inputs."""

from __future__ import annotations

import hashlib
from pathlib import Path

TRUSTED_SPECS = Path("/tests/data/specs")
TRUSTED_WEIGHTS = Path("/tests/data/weights.json")
APP_SPECS = Path("/app/specs")
APP_WEIGHTS = Path("/app/model/weights.json")


def digest_tree(root: Path) -> dict[str, str]:
    digests: dict[str, str] = {}
    if not root.exists():
        return digests
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            digests[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return digests


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_static_inputs_match_trusted() -> None:
    """Compare live specs/model inputs to verifier-owned copies under /tests/data."""
    assert digest_tree(APP_SPECS) == digest_tree(
        TRUSTED_SPECS
    ), "Static specs under /app/specs do not match verifier baseline"
    assert file_digest(APP_WEIGHTS) == file_digest(
        TRUSTED_WEIGHTS
    ), "Model weights under /app/model do not match verifier baseline"


def verify_static_inputs_unchanged() -> None:
    """Worker must leave specs and model weights identical to the verifier baseline."""
    verify_static_inputs_match_trusted()
