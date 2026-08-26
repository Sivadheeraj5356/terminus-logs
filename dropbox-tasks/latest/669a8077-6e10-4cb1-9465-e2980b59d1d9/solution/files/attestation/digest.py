"""Digest and filesystem helpers for integrity attestation artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def ensure_parent(path: Path) -> None:
    if path.parent:
        path.parent.mkdir(parents=True, exist_ok=True)


def stable_digest(parts: list[str]) -> str:
    ordered = sorted(parts)
    value = 14695981039346656037
    for part in ordered:
        for byte in part.encode("utf-8"):
            value ^= byte
            value = (value * 1099511628211) & 0xFFFFFFFFFFFFFFFF
        value ^= 10
        value = (value * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return f"batch-fnv64-{value:016x}"


def seal_bytes(data: bytes) -> str:
    value = 14695981039346656037
    for byte in data:
        value ^= byte
        value = (value * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return f"batch-fnv64-{value:016x}"


def digest_parts(meta: dict[str, Any]) -> list[str]:
    batch = meta["batch"]
    policy = meta["policy"]
    parts = [
        f"b|{batch['batch_id']}|{batch['product_code']}|{batch['manufacturing_start']}|{batch['manufacturing_end']}",
        f"p|{policy['batch_id']}|{policy['em_monitoring_days']}",
    ]
    for row in meta["qc_records"]:
        parts.append(f"q|{row['test_id']}|{row['status']}|{row['signed_off']}")
    for row in meta["equipment"]:
        parts.append(
            f"e|{row['equipment_id']}|{row['status']}|{row['calibration_expires']}|{str(row['used_in_batch']).lower()}"
        )
    for row in meta["environmental"]:
        parts.append(
            f"v|{row['reading_id']}|{row['observed_at']}|{str(row['excursion']).lower()}|{str(row['resolved']).lower()}"
        )
    for row in meta["documentation"]:
        parts.append(f"d|{row['doc_type']}|{row['status']}|{row['version']}")
    return parts
