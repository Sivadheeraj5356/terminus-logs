"""Hardlink reconstruction helpers."""

from __future__ import annotations

import os
from pathlib import Path


class HardlinkRegistry:
    def __init__(self) -> None:
        self._first_path: dict[str, Path] = {}

    def remember(self, key: str, path: Path) -> None:
        if key not in self._first_path:
            self._first_path[key] = path

    def first_path(self, key: str) -> Path | None:
        return self._first_path.get(key)

    def link_or_copy(self, key: str, dest: Path) -> None:
        first = self.first_path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if first is None:
            raise RuntimeError(f"missing hardlink anchor for {key}")
        if dest.exists() or dest.is_symlink():
            dest.unlink()
        os.link(first, dest)

    def same_inode(self, left: Path, right: Path) -> bool:
        try:
            return os.path.samefile(left, right)
        except OSError:
            return False
