"""Integrity staging capsule construction and persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from attestation.digest import digest_parts, ensure_parent, stable_digest
from trust.policy import evaluate_all


def build_snapshot(meta: dict[str, Any]) -> dict[str, Any]:
    gate_results = evaluate_all(meta)
    return {
        "schema_version": 1,
        "batch_id": meta["batch"]["batch_id"],
        "generated_at": meta["policy"]["generated_at"],
        "metadata_digest": stable_digest(digest_parts(meta)),
        "gate_results": gate_results,
    }


def persist_snapshot(path: Path, snapshot: dict[str, Any]) -> None:
    ensure_parent(path)
    text = json.dumps(snapshot, separators=(",", ":"))
    path.write_text(f"{text}\n", encoding="utf-8")
