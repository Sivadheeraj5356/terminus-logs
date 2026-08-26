"""Issuance modes for lot-release integrity attestation."""

from __future__ import annotations

import json
import os
from pathlib import Path

from attestation.ledger import LEDGER_PATH, bump_and_persist
from attestation.publish import publish_from_stage
from attestation.snapshot import build_snapshot, persist_snapshot
from dossier.loader import load_metadata


def _arg_value(args: list[str], flag: str) -> str | None:
    for index, token in enumerate(args):
        if token == flag and index + 1 < len(args):
            return args[index + 1]
    return None


def metadata_dir(args: list[str]) -> Path:
    override = os.environ.get("BATCH_METADATA_DIR", "")
    if override:
        path = Path(override)
        if not path.is_absolute():
            raise ValueError("BATCH_METADATA_DIR must be absolute")
        return path
    value = _arg_value(args, "--metadata")
    if value is None:
        raise ValueError("missing --metadata")
    path = Path(value)
    if not path.is_absolute():
        raise ValueError("--metadata must be absolute")
    return path


def run(args: list[str]) -> int:
    if not args:
        raise ValueError("missing command")
    command = args[0]
    if command == "census":
        meta = load_metadata(metadata_dir(args))
        payload = {
            "batch_id": meta["batch"]["batch_id"],
            "qc_count": len(meta["qc_records"]),
            "equipment_count": len(meta["equipment"]),
            "environmental_count": len(meta["environmental"]),
            "documentation_count": len(meta["documentation"]),
        }
        print(json.dumps(payload, separators=(",", ":")))
        return 0
    if command == "attest-release":
        meta = load_metadata(metadata_dir(args))
        stage_value = _arg_value(args, "--stage")
        output_value = _arg_value(args, "--output")
        if stage_value is None:
            raise ValueError("missing --stage")
        if output_value is None:
            raise ValueError("missing --output")
        stage = Path(stage_value)
        output = Path(output_value)
        if not stage.is_absolute() or not output.is_absolute():
            raise ValueError("stage and output must be absolute")
        snapshot = build_snapshot(meta)
        persist_snapshot(stage, snapshot)
        ledger = bump_and_persist(
            Path(LEDGER_PATH),
            snapshot["batch_id"],
            snapshot["metadata_digest"],
        )
        report = publish_from_stage(stage, output, meta, ledger["evaluation_seq"])
        return 0 if report["release_ready"] else 1
    raise ValueError("unknown command")
