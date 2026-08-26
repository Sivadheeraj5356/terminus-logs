"""Protected pre-run input snapshot helpers."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

REQUIRED_FILES = (
    "devices.json",
    "attestation_keys.json",
    "reference_policies.json",
    "event_logs.json",
    "nonce_challenges.json",
    "quote_requests.ndjson",
    "policy.json",
)


@dataclass(frozen=True)
class ProtectedInputSnapshot:
    files: dict[str, bytes]
    digests: dict[str, str]

    def get(self, name: str) -> bytes:
        return self.files[name]


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def capture_from_dir(data_dir: Path | str) -> ProtectedInputSnapshot:
    root = Path(data_dir)
    files: dict[str, bytes] = {}
    digests: dict[str, str] = {}
    for name in REQUIRED_FILES:
        path = root / name
        if not path.is_file():
            raise FileNotFoundError(f"missing required input: {name}")
        data = path.read_bytes()
        files[name] = data
        digests[name] = _sha256_hex(data)
    return ProtectedInputSnapshot(files=files, digests=digests)


def verify_unchanged(snapshot: ProtectedInputSnapshot, data_dir: Path | str) -> None:
    root = Path(data_dir)
    for name, expected in snapshot.files.items():
        path = root / name
        if not path.is_file():
            raise RuntimeError(f"input mutated/deleted: {name}")
        actual = path.read_bytes()
        if actual != expected:
            raise RuntimeError(f"input mutated: {name}")
        if _sha256_hex(actual) != snapshot.digests[name]:
            raise RuntimeError(f"input digest mismatch: {name}")


def mutation_detected(snapshot: ProtectedInputSnapshot, data_dir: Path | str) -> bool:
    try:
        verify_unchanged(snapshot, data_dir)
        return False
    except RuntimeError:
        return True
