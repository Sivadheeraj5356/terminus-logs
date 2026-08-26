"""Public contract helpers for CT PKI bundles under /app."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import ct_merkle_kernel  # noqa: F401 — contract parity reference surface


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def parse_rfc3339(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def trusted_roots(bundle: Path) -> set[str]:
    doc_roots = {"ROOT-TRUST-01"}
    p = bundle / "trusted_roots.json"
    if p.is_file():
        data = json.loads(p.read_text(encoding="utf-8"))
        return set(data.get("trusted_roots", []))
    return doc_roots


def merkle_parent(left: str, right: str) -> str:
    return hashlib.sha256(bytes.fromhex(left) + bytes.fromhex(right)).hexdigest()


def verify_merkle_path(leaf_hash: str, leaf_index: int, path: list[str], root_hash: str) -> bool:
    cur = leaf_hash
    idx = leaf_index
    for sibling in path:
        if idx % 2 == 0:
            cur = merkle_parent(cur, sibling)
        else:
            cur = merkle_parent(sibling, cur)
        idx //= 2
    return cur == root_hash


def manifest_digest_ok(bundle: Path) -> bool:
    manifest = bundle / "manifests/bundle.sha256"
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        want = line[:64]
        rel = line[64:].lstrip()
        got = hashlib.sha256((bundle / rel).read_bytes()).hexdigest()
        if got != want:
            return False
    return True
