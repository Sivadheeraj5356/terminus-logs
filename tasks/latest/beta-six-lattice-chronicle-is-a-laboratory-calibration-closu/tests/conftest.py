"""Install hidden probe fixtures and scrub temper state before pytest."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

CAPTURE = Path("/app/state/dsc-peak-capture.json")
RESIDUAL = Path("/app/state/torque-residual-snapshot.json")
SEAL = Path("/app/state/polymorph-walk-seal.json")
MANIFEST = Path("/app/state/chronicle-bind-manifest.json")
SPINE = Path("/app/state/hold-spine-ledger.json")
ATLAS = Path("/app/output/lattice-chronicle-report.json")
AUDIT = Path("/app/var/chronicle-audit.log.jsonl")
EPOCH = Path("/app/var/walk_epoch")
TEST_DIR = Path(__file__).resolve().parent


def pytest_configure(config) -> None:
    for install_script in sorted(TEST_DIR.glob("install_*.sh")):
        subprocess.run(["bash", str(install_script)], check=False)
        break


@pytest.fixture(autouse=True)
def scrub_b6lc_state() -> None:
    for path in (CAPTURE, RESIDUAL, SEAL, ATLAS, MANIFEST, SPINE):
        if path.exists():
            path.unlink()
    if AUDIT.exists():
        AUDIT.unlink()
    EPOCH.parent.mkdir(parents=True, exist_ok=True)
    EPOCH.write_text("1\n", encoding="utf-8")
    yield
    for path in (CAPTURE, RESIDUAL, SEAL, ATLAS, MANIFEST, SPINE):
        if path.exists():
            path.unlink()
    if AUDIT.exists():
        AUDIT.unlink()
    if EPOCH.is_file():
        EPOCH.write_text("1\n", encoding="utf-8")
