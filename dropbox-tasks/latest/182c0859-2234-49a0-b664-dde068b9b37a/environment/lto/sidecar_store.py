"""Write thin summary sidecars after object emission."""

from __future__ import annotations

import json
import time
from pathlib import Path

from lto.graph_digest import import_hash
from lto.module_index import GEN_SENSITIVE, source_name


def persist_sidecar(
    module: str,
    src_root: Path,
    work_root: Path,
    obj_root: Path,
    lto_root: Path,
    link_epoch: int = 0,
) -> Path:
    src_path = src_root / source_name(module)
    obj_path = obj_root / f"{module}.o"
    digest = import_hash(module, src_root, work_root)
    payload = {
        "module": module,
        "import_hash": digest,
        "abi_tag": "",
        "object_sha256": _sha(obj_path) if obj_path.is_file() else "",
        "source_mtime": src_path.stat().st_mtime if src_path.is_file() else 0.0,
        "link_epoch": link_epoch if module in GEN_SENSITIVE else 0,
        "written_at": time.time(),
    }
    lto_root.mkdir(parents=True, exist_ok=True)
    out = lto_root / f"{module}.summary.json"
    out.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    return out


def _sha(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()
