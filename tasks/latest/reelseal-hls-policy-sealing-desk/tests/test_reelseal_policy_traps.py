"""Hidden verifier-fixture traps for ReelSeal Gin policy epoch custody."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

import pytest

API = os.environ.get("REELSEAL_API", "http://127.0.0.1:8742")

def test_hidden_verifier_fixtures_roster_epoch_skew_trap():
    """Hidden /opt/verifier-fixtures roster epoch traps resolve when expected_epoch drifts."""
    hidden = Path("/opt/verifier-fixtures/roster-epoch8.json")
    assert hidden.is_file(), "missing /opt/verifier-fixtures roster trap"
    roster = json.loads(hidden.read_text(encoding="utf-8"))
    assert roster["epoch"] == 8
    # With default API (epoch 7) expected 8 would skew; probe uses fixture content as trap oracle
    assert roster["epoch"] != 7
    req = urllib.request.Request(
        f"{API}/v1/profiles/resolve",
        data=json.dumps({"profile_id": "reel-std", "expected_epoch": 8}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=5)
        pytest.fail("default API epoch 7 must reject expected_epoch 8")
    except urllib.error.HTTPError as exc:
        assert exc.code == 409

def test_hidden_verifier_fixtures_path_contract_trap():
    """Verifier-fixtures under /opt/verifier-fixtures remain authoritative for alternate roster traps."""
    root = Path("/opt/verifier-fixtures")
    assert root.is_dir()
    names = {p.name for p in root.iterdir()}
    assert "roster-epoch8.json" in names

