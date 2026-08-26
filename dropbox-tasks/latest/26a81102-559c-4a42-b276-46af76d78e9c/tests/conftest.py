"""Shared pytest fixtures for CipherGrid cipherleague puzzle scoring."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cipher_ref  # noqa: E402

APP_ROOT = Path("/app")
CIPHERLEAGUE = str(APP_ROOT / "bin" / "cipherleague")
STOCK_ARCHIVE = APP_ROOT / "data" / "season4"
SCHEMA_PATH = APP_ROOT / "schema" / "ciphergrid-puzzle-league.schema.json"
CHAIN_TIP = APP_ROOT / "var" / "match_chain_tip.txt"


def clear_chain_tip() -> None:
    CHAIN_TIP.unlink(missing_ok=True)


def run_cli(*args: str, timeout: float = 60.0) -> subprocess.CompletedProcess:
    return subprocess.run(
        [CIPHERLEAGUE, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def run_evaluate(archive: str | Path, out_path: str | Path) -> dict:
    proc = run_cli("score", "--archive", str(archive), "--out", str(out_path))
    assert proc.returncode == 0, proc.stderr or proc.stdout
    return json.loads(Path(out_path).read_text())


def run_evaluate_fresh(archive: str | Path, out_path: str | Path) -> dict:
    clear_chain_tip()
    return run_evaluate(archive, out_path)


def ref_evaluate(archive: str | Path, *, prior_tip: str = "") -> dict:
    return cipher_ref.evaluate_archive(archive, prior_tip=prior_tip, persist_tip=False)


@pytest.fixture(scope="session")
def stock_archive() -> Path:
    return STOCK_ARCHIVE


@pytest.fixture(scope="session")
def stock_report(tmp_path_factory) -> dict:
    clear_chain_tip()
    out = tmp_path_factory.mktemp("reports") / "stock.json"
    return run_evaluate(STOCK_ARCHIVE, out)


@pytest.fixture(scope="session")
def ref_stock() -> dict:
    return ref_evaluate(STOCK_ARCHIVE, prior_tip="")
