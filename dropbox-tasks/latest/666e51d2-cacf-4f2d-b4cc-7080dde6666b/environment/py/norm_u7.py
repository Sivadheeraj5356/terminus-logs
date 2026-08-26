"""Reference normalization helpers for convergence_run.v1 fingerprint lines."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def slim_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [
        {
            "run_label": ev["run_label"],
            "phase": ev["phase"],
            "segment_id": ev["segment_id"],
            "era": ev["era"],
            "attach_id": ev["attach_id"],
            "outcome": ev["outcome"],
        }
        for ev in entries
    ]
    rows.sort(key=lambda r: (r["run_label"], r["segment_id"], r["phase"]))
    return rows


def entry_hash(entries: list[dict[str, Any]]) -> str:
    raw = json.dumps(slim_entries(entries), separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()
