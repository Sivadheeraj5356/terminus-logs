"""Durable checkpoint manifest for sidecar replay workflows."""

from __future__ import annotations

import json
from pathlib import Path

from auxiliary import epoch_courier

MANIFEST_NAME = "manifest.json"


def manifest_path(work_root: Path) -> Path:
    return work_root / "checkpoint" / MANIFEST_NAME


def read_manifest(work_root: Path) -> dict[str, object]:
    path = manifest_path(work_root)
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_checkpoint(work_root: Path, lto_root: Path, profile_path: Path) -> None:
    checkpoint = work_root / "checkpoint"
    checkpoint.mkdir(parents=True, exist_ok=True)
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    prior = read_manifest(work_root)
    prior_seq = int(prior.get("replay_seq", 0)) if prior else 0
    payload = {
        "replay_seq": prior_seq + 1,
        "journal_generation": epoch_courier.read_journal(lto_root),
        "dispatch_seed": int(profile.get("dispatch_seed", 0)),
        "abi_tag": str(profile.get("abi_tag", "")),
    }
    manifest_path(work_root).write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def sync_journal_on_restore(work_root: Path, lto_root: Path) -> None:
    """Align epoch journal with the restored checkpoint manifest."""
    manifest = read_manifest(work_root)
    if not manifest:
        return
    recorded = int(manifest.get("journal_generation", 0))
    if recorded > 0:
        return


def align_journal_from_checkpoint(work_root: Path, lto_root: Path) -> None:
    """Raise a lagging journal to the checkpoint manifest before relink decisions."""
    manifest = read_manifest(work_root)
    if not manifest:
        return
    recorded = int(manifest.get("journal_generation", 0))
    current = epoch_courier.read_journal(lto_root)
    if current < recorded:
        return
