"""Read tbundle JSON archives."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from archive.formats import TBUNDLE_FORMAT


@dataclass(frozen=True)
class ArchiveEntry:
    path: str
    entry_type: str
    mode: int | None = None
    uid: int | None = None
    gid: int | None = None
    content: bytes | None = None
    symlink_target: str | None = None
    hardlink_key: str | None = None
    xattr: dict[str, str] | None = None
    acl: list[str] | None = None


def load_archive(path: Path) -> list[ArchiveEntry]:
    data = json.loads(path.read_text())
    if data.get("format") != TBUNDLE_FORMAT:
        raise ValueError(f"unsupported archive format in {path}")
    entries: list[ArchiveEntry] = []
    for raw in data.get("entries", []):
        content = None
        if raw.get("content_b64") is not None:
            content = base64.b64decode(raw["content_b64"])
        entries.append(
            ArchiveEntry(
                path=raw["path"],
                entry_type=raw["type"],
                mode=int(raw["mode"], 8) if "mode" in raw else None,
                uid=raw.get("uid"),
                gid=raw.get("gid"),
                content=content,
                symlink_target=raw.get("symlink_target"),
                hardlink_key=raw.get("hardlink_key"),
                xattr=dict(raw.get("xattr", {})),
                acl=list(raw.get("acl", [])),
            )
        )
    return entries


def archive_entry_map(path: Path) -> dict[str, ArchiveEntry]:
    return {entry.path: entry for entry in load_archive(path)}


def manifest_payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())
