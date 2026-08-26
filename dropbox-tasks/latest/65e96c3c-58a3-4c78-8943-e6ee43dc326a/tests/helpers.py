"""Independent fixture loading and expected-packet derivation for the verifier."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import tomllib
from pathlib import Path
from typing import Any

import reference


APP_DIR = Path(os.environ.get("APP_DIR", "/app"))
FIXTURE_DIR = APP_DIR / "fixtures" / "visible"
OUTPUT_DIR = Path(
    os.environ.get("OUT_DIR", str(APP_DIR / "out" / "cipherwave-incident"))
)


def sha256(data: bytes) -> str:
    """Return lowercase SHA-256 for byte-integrity assertions."""

    return hashlib.sha256(data).hexdigest()


def load_registry(path: Path) -> dict[str, bytes]:
    """Strictly decode registry manifest entries into logical lookup bytes."""

    manifest = json.loads(path.read_bytes())
    assert list(manifest) == ["bucket", "entries"]
    assert manifest["bucket"] == "keys"
    records: dict[str, bytes] = {}
    previous: bytes | None = None
    for entry in manifest["entries"]:
        assert list(entry) == ["key", "valueBase64"]
        key = entry["key"]
        key_bytes = key.encode("utf-8")
        assert previous is None or previous < key_bytes
        records[key] = base64.b64decode(entry["valueBase64"], validate=True)
        previous = key_bytes
    return records


def derive_expected() -> dict[str, Any]:
    """Recompute the complete incident packet without importing submitted code."""

    profile_path = FIXTURE_DIR / "profile.toml"
    trust_path = FIXTURE_DIR / "trust.json"
    registry_path = FIXTURE_DIR / "registry.json"
    catalog_path = FIXTURE_DIR / "catalog.json"
    guardian_trust_path = FIXTURE_DIR / "guardian-trust.json"
    rollout_ledger_path = FIXTURE_DIR / "rollout-ledger.json"
    profile_bytes = profile_path.read_bytes()
    trust_bytes = trust_path.read_bytes()
    registry_bytes = registry_path.read_bytes()
    catalog_bytes = catalog_path.read_bytes()
    result = reference.derive_all(
        profile=tomllib.loads(profile_bytes.decode("utf-8")),
        trust=json.loads(trust_bytes),
        registry_records=load_registry(registry_path),
        catalog=json.loads(catalog_bytes),
        guardian_trust=json.loads(guardian_trust_path.read_bytes()),
        rollout_ledger=json.loads(rollout_ledger_path.read_bytes()),
        media=reference.load_media_tree(FIXTURE_DIR / "media"),
        profile_bytes=profile_bytes,
        trust_bytes=trust_bytes,
        registry_bytes=registry_bytes,
        catalog_bytes=catalog_bytes,
    )
    result["bytes"] = {
        "custody.json": reference.artifact_bytes(result["custody"]),
        "evidence.json": reference.artifact_bytes(result["evidence"]),
        "checkpoint-frontier.jsonl": result["checkpointFrontierBytes"],
        "authorization-proof.json": reference.artifact_bytes(result["authorization"]),
        "rotation-certificate.json": reference.artifact_bytes(result["certificate"]),
        "ffmpeg-plan.toml": result["planToml"],
    }
    return result


def read_packet() -> dict[str, bytes]:
    """Read exactly the six required deliverables."""

    assert OUTPUT_DIR.is_dir(), f"missing output directory: {OUTPUT_DIR}"
    names = sorted(path.name for path in OUTPUT_DIR.iterdir())
    assert names == [
        "authorization-proof.json",
        "checkpoint-frontier.jsonl",
        "custody.json",
        "evidence.json",
        "ffmpeg-plan.toml",
        "rotation-certificate.json",
    ]
    return {name: (OUTPUT_DIR / name).read_bytes() for name in names}
