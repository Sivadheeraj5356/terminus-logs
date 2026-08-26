"""Id-map translation for rootless ownership recording."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


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
