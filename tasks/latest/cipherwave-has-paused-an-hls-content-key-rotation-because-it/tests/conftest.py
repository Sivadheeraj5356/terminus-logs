"""Shared verifier fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

TEST_DIR = Path(__file__).resolve().parent
if str(TEST_DIR) not in sys.path:
    sys.path.insert(0, str(TEST_DIR))

from helpers import derive_expected, read_packet  # noqa: E402


# The conventional single-step entry point imports these behavioral tests.
# Ignore their source modules during directory discovery to avoid duplicate runs.
collect_ignore = [
    "test_checkpoint_frontier.py",
    "test_packet_integrity.py",
    "test_security_audit.py",
]


@pytest.fixture(scope="session")
def expected():
    """Provide the independently derived incident result."""

    return derive_expected()


@pytest.fixture(scope="session")
def packet():
    """Provide the submitted six-file packet."""

    return read_packet()
