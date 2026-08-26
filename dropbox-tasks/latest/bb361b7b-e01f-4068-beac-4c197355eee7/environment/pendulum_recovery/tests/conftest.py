"""Shared fixtures for report CLI tests."""

from __future__ import annotations

import os
import sys

import pytest

BUILDER_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "builder"))
if BUILDER_ROOT not in sys.path:
    sys.path.insert(0, BUILDER_ROOT)


@pytest.fixture(scope="session")
def seeded_db(tmp_path_factory):
    """Build a fresh seeded database in a temp dir and return its path."""

    import seed_db

    db_path = str(tmp_path_factory.mktemp("seed") / "pendulum_captures.duckdb")
    seed_db.build_database(db_path)
    return db_path
