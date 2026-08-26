#!/usr/bin/env python3
"""Derive the fixed Cipherwave incident packet from its immutable authorities."""

from __future__ import annotations

import base64
import json
import os
import shutil
import tomllib
from pathlib import Path

import reference


def load_registry(path: Path) -> dict[str, bytes]:
    """Decode the transport-neutral logical registry export."""

    manifest = json.loads(path.read_bytes())
    if set(manifest) != {"bucket", "entries"} or manifest["bucket"] != "keys":
        raise ValueError("invalid registry manifest")
    entries = manifest["entries"]
    if not isinstance(entries, list):
        raise ValueError("invalid registry entries")
    records: dict[str, bytes] = {}
    previous: bytes | None = None
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"key", "valueBase64"}:
            raise ValueError("invalid registry entry")
        key = entry["key"]
        encoded = entry["valueBase64"]
        if not isinstance(key, str) or not isinstance(encoded, str):
            raise ValueError("invalid registry entry types")
        key_bytes = key.encode("utf-8")
        if previous is not None and key_bytes <= previous:
            raise ValueError("registry entries are not strictly sorted")
        try:
            value = base64.b64decode(encoded, validate=True)
        except Exception as exc:
            raise ValueError("invalid registry value encoding") from exc
        records[key] = value
        previous = key_bytes
    return records


def main() -> None:
    """Load the fixed incident, derive all bindings, and atomically publish the packet."""

    app_dir = Path(os.environ.get("APP_DIR", "/app"))
    fixture_dir = app_dir / "fixtures" / "visible"
    output_dir = Path(
        os.environ.get("OUT_DIR", str(app_dir / "out" / "cipherwave-incident"))
    )

    profile_path = fixture_dir / "profile.toml"
    trust_path = fixture_dir / "trust.json"
    registry_path = fixture_dir / "registry.json"
    catalog_path = fixture_dir / "catalog.json"
    guardian_trust_path = fixture_dir / "guardian-trust.json"
    rollout_ledger_path = fixture_dir / "rollout-ledger.json"

    profile_bytes = profile_path.read_bytes()
    trust_bytes = trust_path.read_bytes()
    registry_bytes = registry_path.read_bytes()
    catalog_bytes = catalog_path.read_bytes()
    guardian_trust_bytes = guardian_trust_path.read_bytes()
    rollout_ledger_bytes = rollout_ledger_path.read_bytes()
    result = reference.derive_all(
        profile=tomllib.loads(profile_bytes.decode("utf-8")),
        trust=json.loads(trust_bytes),
        registry_records=load_registry(registry_path),
        catalog=json.loads(catalog_bytes),
        guardian_trust=json.loads(guardian_trust_bytes),
        rollout_ledger=json.loads(rollout_ledger_bytes),
        media=reference.load_media_tree(fixture_dir / "media"),
        profile_bytes=profile_bytes,
        trust_bytes=trust_bytes,
        registry_bytes=registry_bytes,
        catalog_bytes=catalog_bytes,
    )

    parent = output_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    staging = parent / f".{output_dir.name}.tmp"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir()
    (staging / "custody.json").write_bytes(reference.artifact_bytes(result["custody"]))
    (staging / "evidence.json").write_bytes(reference.artifact_bytes(result["evidence"]))
    (staging / "checkpoint-frontier.jsonl").write_bytes(
        result["checkpointFrontierBytes"]
    )
    (staging / "authorization-proof.json").write_bytes(
        reference.artifact_bytes(result["authorization"])
    )
    (staging / "rotation-certificate.json").write_bytes(
        reference.artifact_bytes(result["certificate"])
    )
    (staging / "ffmpeg-plan.toml").write_bytes(result["planToml"])
    if output_dir.exists():
        shutil.rmtree(output_dir)
    staging.replace(output_dir)


if __name__ == "__main__":
    main()
