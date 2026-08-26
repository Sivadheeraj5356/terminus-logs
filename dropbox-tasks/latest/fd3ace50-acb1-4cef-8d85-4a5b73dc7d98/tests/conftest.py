"""Pytest configuration for VLAN Segmentation Enforcer tests."""

import json
import os

import pytest

RESULT_PATH = "/app/output/enforcement_result.json"


@pytest.fixture(scope="session")
def result_path():
    """Return the path to the enforcement result JSON file."""
    if not os.path.exists(RESULT_PATH):
        pytest.skip("Enforcement result not found. Run solve.sh first.")
    return RESULT_PATH


@pytest.fixture(scope="session")
def result():
    """Load the enforcement result JSON produced by the engine."""
    if not os.path.exists(RESULT_PATH):
        pytest.skip("Enforcement result not found. Run solve.sh first.")
    with open(RESULT_PATH) as f:
        return json.load(f)
