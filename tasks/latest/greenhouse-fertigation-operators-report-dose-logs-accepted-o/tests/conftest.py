"""Shared pytest fixtures for fertigation CLI verifier."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def zone_id() -> str:
    return "zone-a"


@pytest.fixture
def shared_db(tmp_path: Path) -> Path:
    return tmp_path / "shared-fertigation.db"
