"""Manifest epoch/seal store helpers."""

import hashlib
import json
import tomllib


def digest_payload(payload: dict) -> str:
    """Return a lowercase sha256 hex digest for a compact JSON payload."""
    data = json.dumps(payload, separators=(",", ":")).encode()
    return hashlib.sha256(data).hexdigest()


def load_profile_toml(path: str) -> dict:
    """Load a profile descriptor with tomllib, matching the verifier loader."""
    with open(path, "rb") as handle:
        return tomllib.load(handle)


def profile_runs(path: str) -> list:
    """Return the ordered run list declared by a profile descriptor."""
    return list(load_profile_toml(path).get("runs", []))
