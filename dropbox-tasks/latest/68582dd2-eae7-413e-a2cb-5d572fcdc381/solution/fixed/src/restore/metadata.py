"""Extended metadata application for restored paths."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from restore.constants import ACL_XATTR, GID_XATTR, UID_XATTR
from restore.idmap import MappedOwnership


def apply_mode(path: Path, mode: int) -> None:
    os.chmod(path, mode)


def apply_ownership(path: Path, mapped: MappedOwnership) -> None:
    os.setxattr(path, UID_XATTR, str(mapped.uid).encode())
    os.setxattr(path, GID_XATTR, str(mapped.gid).encode())


def apply_user_xattrs(path: Path, xattr: dict[str, str]) -> None:
    for key, value in sorted(xattr.items()):
        if key in {UID_XATTR, GID_XATTR, ACL_XATTR}:
            continue
        os.setxattr(path, key, value.encode())


def apply_acl(path: Path, acl: list[str]) -> None:
    if acl:
        os.setxattr(path, ACL_XATTR, json.dumps(acl).encode())


def collect_metadata_record(
    path: str,
    mapped: MappedOwnership,
    xattr: dict[str, str],
    acl: list[str],
) -> dict[str, Any]:
    keys = sorted(set(xattr) | {UID_XATTR, GID_XATTR} | ({ACL_XATTR} if acl else set()))
    return {
        "path": path,
        "mapped_uid": mapped.uid,
        "mapped_gid": mapped.gid,
        "xattr_keys": keys,
        "acl": list(acl),
    }


def apply_metadata(
    path: Path,
    rel_path: str,
    mode: int,
    mapped: MappedOwnership,
    xattr: dict[str, str],
    acl: list[str],
) -> dict[str, Any]:
    if not path.exists() and not path.is_symlink():
        raise FileNotFoundError(rel_path)
    apply_mode(path, mode)
    apply_user_xattrs(path, xattr)
    apply_acl(path, acl)
    apply_ownership(path, mapped)
    return collect_metadata_record(rel_path, mapped, xattr, acl)
