"""Shared subprocess and path helpers for CT PKI pytest and contract checks."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

CTPKI = Path("/app/bin/ctpki")
BUNDLE_ALPHA = Path("/app/fixtures/bundle-migration-alpha")
SNAPSHOT = Path("/app/state/pki-evidence/ct_merkle_snapshot.json")
DISPOSITION = Path("/app/state/pki-evidence/disposition_matrix.json")
LEDGER = Path("/app/output/published_ct_ledger.json")
PUBLISH_EPOCH = Path("/app/state/pki-evidence/publish_epoch.json")

ALPHA_TRUSTED = ["SER-DUP", "SER-LEGACY"]
_HOLDOUT_ENV = "CTPKI_HOLDOUT_DIR"


def stage_holdout_bundle(test_tree: Path) -> Path:
    """Copy verifier holdout fixtures from the test tree into a temp directory."""
    existing = os.environ.get(_HOLDOUT_ENV)
    if existing:
        return Path(existing)
    src = test_tree / "tb3_fixtures"
    dest = Path(tempfile.mkdtemp(prefix="ct-holdout-"))
    if src.is_dir():
        shutil.copytree(src, dest, dirs_exist_ok=True)
    os.environ[_HOLDOUT_ENV] = str(dest)
    return dest


def holdout_bundle() -> Path:
    path = os.environ.get(_HOLDOUT_ENV)
    if not path:
        raise RuntimeError("holdout bundle not staged — pytest session fixture must run first")
    return Path(path)


def run_cmd(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


def fresh_state() -> None:
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    for path in (SNAPSHOT, DISPOSITION, LEDGER, PUBLISH_EPOCH):
        if path.exists():
            path.unlink()


def run_pipeline(bundle: Path) -> None:
    fresh_state()
    run_cmd(
        [
            str(CTPKI),
            "attest",
            "--bundle",
            str(bundle),
            "--snapshot",
            str(SNAPSHOT),
            "--report",
            str(DISPOSITION),
        ]
    )
    run_cmd(
        [
            str(CTPKI),
            "publish",
            "--report",
            str(DISPOSITION),
            "--snapshot",
            str(SNAPSHOT),
            "--out",
            str(LEDGER),
        ]
    )


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
