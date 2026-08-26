"""Independent restore expectation model for verifier use only."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


UID_XATTR = "user.restore.uid"
GID_XATTR = "user.restore.gid"
ACL_XATTR = "user.restore.acl"


@dataclass(frozen=True)
class MappedOwnership:
    uid: int
    gid: int


@dataclass
class IdMap:
    subuid_base: int
    subgid_base: int
    fallback_uid: int
    fallback_gid: int
    overrides: dict[tuple[int, int], tuple[int, int]]

    @classmethod
    def load(cls, path: Path) -> "IdMap":
        data = tomllib.loads(path.read_text())
        defaults = data.get("defaults", {})
        overrides: dict[tuple[int, int], tuple[int, int]] = {}
        for row in data.get("override", []):
            key = (int(row["source_uid"]), int(row["source_gid"]))
            overrides[key] = (int(row["uid"]), int(row["gid"]))
        return cls(
            subuid_base=int(defaults.get("subuid_base", 100000)),
            subgid_base=int(defaults.get("subgid_base", 100000)),
            fallback_uid=int(defaults.get("fallback_uid", 65534)),
            fallback_gid=int(defaults.get("fallback_gid", 65534)),
            overrides=overrides,
        )

    def map_owner(self, source_uid: int | None, source_gid: int | None) -> MappedOwnership:
        uid = 0 if source_uid is None else int(source_uid)
        gid = 0 if source_gid is None else int(source_gid)
        override = self.overrides.get((uid, gid))
        if override is not None:
            return MappedOwnership(uid=override[0], gid=override[1])
        return MappedOwnership(uid=self.subuid_base + uid, gid=self.subgid_base + gid)


def normalize_rel_path(prefix: str, path: str) -> str:
    joined = path.lstrip("/")
    if prefix:
        joined = f"{prefix.rstrip('/')}/{path.lstrip('/')}"
    parts: list[str] = []
    for part in joined.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return "/".join(parts)


def load_archive(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text())
    return list(data.get("entries", []))


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def expected_log(
    manifest_path: Path,
    archives_dir: Path,
    idmap_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    archive_path = archives_dir / manifest["archive"]
    prefix = manifest.get("restore_prefix", "")
    idmap = IdMap.load(idmap_path)
    archive_entries = load_archive(archive_path)
    archive_by_path = {normalize_rel_path("", e["path"]): e for e in archive_entries}

    restored = sorted(
        {
            normalize_rel_path(prefix, e["path"])
            for e in archive_entries
        }
    )

    metadata_applied: list[dict[str, Any]] = []
    for item in sorted(manifest.get("entries", []), key=lambda row: normalize_rel_path(prefix, row["path"])):
        rel = normalize_rel_path(prefix, item["path"])
        archive_entry = archive_by_path.get(normalize_rel_path("", item["path"]))
        source_uid = archive_entry.get("uid") if archive_entry else None
        source_gid = archive_entry.get("gid") if archive_entry else None
        if archive_entry and archive_entry.get("type") == "hardlink":
            key = archive_entry.get("hardlink_key")
            for candidate in archive_entries:
                if candidate.get("hardlink_key") == key and candidate.get("type") == "file":
                    source_uid = candidate.get("uid")
                    source_gid = candidate.get("gid")
                    break
        mapped = idmap.map_owner(source_uid, source_gid)
        xattr = dict(item.get("xattr", {}))
        acl = list(item.get("acl", []))
        keys = sorted(set(xattr) | {UID_XATTR, GID_XATTR} | ({ACL_XATTR} if acl else set()))
        metadata_applied.append(
            {
                "path": rel,
                "mapped_uid": mapped.uid,
                "mapped_gid": mapped.gid,
                "xattr_keys": keys,
                "acl": acl,
            }
        )

    return {
        "schema_version": 1,
        "manifest": manifest_path.name,
        "archive": manifest["archive"],
        "restore_root": str(output_root),
        "status": "ok",
        "entries_restored": restored,
        "metadata_applied": metadata_applied,
    }


def read_xattr(path: Path, key: str) -> str | None:
    try:
        return os.getxattr(path, key).decode()
    except OSError:
        return None


def filesystem_snapshot(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    prefix = manifest.get("restore_prefix", "")
    snapshot: dict[str, Any] = {"paths": {}, "hardlink_groups": {}}
    for item in manifest.get("entries", []):
        rel = normalize_rel_path(prefix, item["path"])
        path = root / rel
        entry: dict[str, Any] = {
            "type": item["type"],
            "mode": oct(path.stat().st_mode & 0o7777)[2:].zfill(4) if path.exists() or path.is_symlink() else None,
            "mapped_uid": int(read_xattr(path, UID_XATTR) or -1),
            "mapped_gid": int(read_xattr(path, GID_XATTR) or -1),
        }
        if item["type"] == "file" or item["type"] == "hardlink":
            entry["content_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            entry["nlink"] = path.stat().st_nlink
            group = item.get("hardlink_group")
            if group:
                snapshot["hardlink_groups"].setdefault(group, []).append(rel)
        if item["type"] == "symlink":
            entry["symlink_target"] = os.readlink(path)
        xattr = {}
        for key, value in item.get("xattr", {}).items():
            got = read_xattr(path, key)
            if got is not None:
                xattr[key] = got
        entry["xattr"] = xattr
        acl_raw = read_xattr(path, ACL_XATTR)
        entry["acl"] = json.loads(acl_raw) if acl_raw else []
        snapshot["paths"][rel] = entry
    for group, paths in snapshot["hardlink_groups"].items():
        inodes = { (root / p).stat().st_ino for p in paths }
        snapshot["hardlink_groups"][group] = {
            "paths": sorted(paths),
            "shared_inode": len(inodes) == 1,
            "nlink": (root / paths[0]).stat().st_nlink if paths else 0,
        }
    return snapshot


def build_generated_archive(
    dest_archive: Path,
    dest_manifest: Path,
    *,
    bundle_name: str,
    restore_prefix: str,
) -> None:
    token = f"generated-{bundle_name}".encode()
    entries = [
        {
            "path": f"svc/{bundle_name}/data.bin",
            "type": "file",
            "mode": "0600",
            "uid": 1001,
            "gid": 1001,
            "content_b64": base64.b64encode(token).decode(),
            "xattr": {"user.svc.bundle": bundle_name},
            "acl": ["user::rw-", "group::---", "other::---"],
            "hardlink_key": f"hl-{bundle_name}",
        },
        {
            "path": f"svc/{bundle_name}/mirror.bin",
            "type": "hardlink",
            "hardlink_key": f"hl-{bundle_name}",
        },
    ]
    dest_archive.write_text(json.dumps({"format": "tbundle-1", "entries": entries}, indent=2) + "\n")
    manifest = {
        "schema_version": 1,
        "archive": dest_archive.name,
        "restore_prefix": restore_prefix,
        "preserve_paths": [],
        "entries": [
            {
                "path": f"svc/{bundle_name}/data.bin",
                "type": "file",
                "mode": "0600",
                "mapped_uid": 101001,
                "mapped_gid": 101001,
                "content_sha256": hashlib.sha256(token).hexdigest(),
                "xattr": {"user.svc.bundle": bundle_name},
                "acl": ["user::rw-", "group::---", "other::---"],
                "hardlink_group": f"hl-{bundle_name}",
            },
            {
                "path": f"svc/{bundle_name}/mirror.bin",
                "type": "hardlink",
                "mode": "0600",
                "mapped_uid": 101001,
                "mapped_gid": 101001,
                "content_sha256": hashlib.sha256(token).hexdigest(),
                "hardlink_group": f"hl-{bundle_name}",
            },
        ],
    }
    dest_manifest.write_text(json.dumps(manifest, indent=2) + "\n")
