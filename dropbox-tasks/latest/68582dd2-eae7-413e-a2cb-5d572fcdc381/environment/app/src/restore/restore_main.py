"""Restore entrypoint."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from archive.reader import ArchiveEntry, archive_entry_map, load_archive, manifest_payload
from restore.hardlinks import HardlinkRegistry
from restore.idmap import IdMap
from restore.metadata import apply_metadata


def normalize_rel_path(prefix: str, path: str) -> str:
    if prefix:
        return f"{prefix.rstrip('/')}/{path.lstrip('/')}"
    return path.lstrip("/")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def prune_managed_paths(root: Path, managed: set[str], preserve: set[str]) -> None:
    if not root.exists():
        root.mkdir(parents=True, exist_ok=True)
        return
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_file() or path.is_symlink():
            path.unlink()
        elif path.is_dir() and not any(child for child in path.iterdir()):
            path.rmdir()


def materialize_entry(
    root: Path,
    rel_path: str,
    entry: ArchiveEntry,
    registry: HardlinkRegistry,
) -> None:
    dest = root / rel_path
    if entry.entry_type == "dir":
        dest.mkdir(parents=True, exist_ok=True)
        return
    if entry.entry_type == "symlink":
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() or dest.is_symlink():
            dest.unlink()
        os.symlink(entry.symlink_target or "", dest)
        return
    if entry.entry_type == "hardlink":
        key = entry.path
        registry.link_or_copy(key, dest)
        return
    if entry.entry_type == "file":
        dest.parent.mkdir(parents=True, exist_ok=True)
        data = entry.content or b""
        dest.write_bytes(data)
        if entry.hardlink_key:
            registry.remember(entry.hardlink_key, dest)
        return
    raise ValueError(f"unsupported entry type {entry.entry_type}")


def execute_restore(
    archives_dir: Path,
    manifest_path: Path,
    output_root: Path,
    idmap_path: Path,
    log_path: Path,
) -> dict[str, Any]:
    manifest = manifest_payload(manifest_path)
    archive_name = manifest["archive"]
    archive_path = archives_dir / archive_name
    prefix = manifest.get("restore_prefix", "")
    preserve = set(manifest.get("preserve_paths", []))
    entries = load_archive(archive_path)
    by_path = archive_entry_map(archive_path)
    idmap = IdMap.load(idmap_path)

    managed: set[str] = set()
    for item in manifest.get("entries", []):
        managed.add(normalize_rel_path(prefix, item["path"]))
    for entry in entries:
        managed.add(normalize_rel_path(prefix, entry.path))

    prune_managed_paths(output_root, managed, preserve)

    registry = HardlinkRegistry()
    restored: list[str] = []
    metadata_records: list[dict[str, Any]] = []

    for entry in entries:
        rel = normalize_rel_path(prefix, entry.path)
        materialize_entry(output_root, rel, entry, registry)
        restored.append(rel)

    for item in manifest.get("entries", []):
        rel = normalize_rel_path(prefix, item["path"])
        archive_entry = by_path.get(item["path"])
        source_uid = archive_entry.uid if archive_entry else None
        source_gid = archive_entry.gid if archive_entry else None
        mapped = idmap.map_owner(source_uid, source_gid)
        mode = int(item["mode"], 8)
        xattr = dict(item.get("xattr", {}))
        acl = list(item.get("acl", []))
        dest = output_root / rel
        record = apply_metadata(dest, rel, mode, mapped, xattr, acl)
        metadata_records.append(record)

    log = {
        "schema_version": 1,
        "manifest": manifest_path.name,
        "archive": archive_name,
        "restore_root": str(output_root),
        "status": "ok",
        "entries_restored": restored,
        "metadata_applied": metadata_records,
    }
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(log, indent=2) + "\n")
    return log


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Restore tbundle archives")
    parser.add_argument("--archives-dir", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--idmap", required=True)
    parser.add_argument("--log", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    execute_restore(
        archives_dir=Path(args.archives_dir),
        manifest_path=Path(args.manifest),
        output_root=Path(args.output),
        idmap_path=Path(args.idmap),
        log_path=Path(args.log),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
