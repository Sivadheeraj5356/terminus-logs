#!/usr/bin/env python3
"""Verifier helpers delegating to reference oracle."""
from __future__ import annotations

from pathlib import Path

from reference_audit import compute_chain_digest, conflict_ids, expected_integrity

PRIMARY_MANIFEST = Path("/app/data/manifest.json")


def primary_expected() -> tuple[list[dict], dict, dict]:
    return expected_integrity(PRIMARY_MANIFEST)


CONFLICT_IDS = sorted(conflict_ids(PRIMARY_MANIFEST))


__all__ = [
    "CONFLICT_IDS",
    "compute_chain_digest",
    "primary_expected",
]
