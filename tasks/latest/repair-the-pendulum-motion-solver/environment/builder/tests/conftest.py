"""Shared fixtures for the pendulum_recovery project tests."""

import os
import sys

import pytest

# Make the builder modules importable when pytest is invoked from the repo root.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture(scope="session")
def seeded_db(tmp_path_factory):
    """Build a fresh seeded database in a temp dir and return its path."""

    import seed_db

    db_path = str(tmp_path_factory.mktemp("seed") / "pendulum_captures.duckdb")
    seed_db.build_database(db_path)
    return db_path
