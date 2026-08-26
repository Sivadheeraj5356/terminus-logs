"""Rebuild agent kernel and stage verifier fixtures before pytest."""

from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path

import pytest

FIXTURE_SRC = Path("/tests") / "verifier-fixtures"
FIXTURE_DST = Path("/opt") / "verifier-fixtures"


def _harden_tree(root: Path) -> None:
    """Make verifier fixtures root-owned and non-writable for the restricted agent."""
    if os.geteuid() != 0:
        return
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        os.chown(current, 0, 0)
        os.chmod(current, 0o555)
        for name in dirnames:
            child = current / name
            os.chown(child, 0, 0)
            os.chmod(child, 0o555)
        for name in filenames:
            child = current / name
            os.chown(child, 0, 0)
            os.chmod(child, 0o444)


@pytest.fixture(scope="session", autouse=True)
def stage_agent_kernel_and_fixtures() -> None:
    """Stage verifier fixtures and publish the traced-build binary.

    test.sh cleans and rebuilds the submitted Rust kernel under the strace
    trace guard (see trace_run.py) before pytest starts, so this fixture only
    copies verifier fixtures and the freshly built binary into place. Fixture
    trees are then locked down so the restricted agent process cannot rewrite
    ground-truth inputs used by overlay tests.
    """
    if FIXTURE_SRC.is_dir():
        FIXTURE_DST.mkdir(parents=True, exist_ok=True)
        for item in FIXTURE_SRC.iterdir():
            dest = FIXTURE_DST / item.name
            if item.is_dir():
                if dest.exists():
                    # Temporarily writable so we can replace staged content.
                    if os.geteuid() == 0:
                        os.chmod(dest, 0o755)
                        for dirpath, _, filenames in os.walk(dest):
                            os.chmod(dirpath, 0o755)
                            for name in filenames:
                                os.chmod(Path(dirpath) / name, 0o644)
                    shutil.rmtree(dest)
                shutil.copytree(item, dest)
            else:
                if dest.exists() and os.geteuid() == 0:
                    os.chmod(dest, 0o644)
                shutil.copy2(item, dest)
        _harden_tree(FIXTURE_DST)
    bin_dir = Path("/app/bin")
    bin_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2("/app/target/release/gaa-extract", bin_dir / "gaa-extract")
    mode = (bin_dir / "gaa-extract").stat().st_mode
    (bin_dir / "gaa-extract").chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    Path("/app/state").mkdir(parents=True, exist_ok=True)
    Path("/app/out").mkdir(parents=True, exist_ok=True)
    agent_uid = int(os.environ.get("TB3_AGENT_UID", "10001"))
    agent_gid = int(os.environ.get("TB3_AGENT_GID", "10001"))
    if os.geteuid() == 0:
        for path in (Path("/app/state"), Path("/app/out"), bin_dir, bin_dir / "gaa-extract"):
            try:
                os.chown(path, agent_uid, agent_gid)
            except OSError:
                pass


@pytest.fixture(autouse=True)
def _agent_writable_tmpdir(tmp_path: Path) -> None:
    """Let the restricted agent uid traverse pytest tmp parents and write outputs."""
    if os.geteuid() != 0:
        return
    uid = int(os.environ.get("TB3_AGENT_UID", "10001"))
    gid = int(os.environ.get("TB3_AGENT_GID", "10001"))
    # /tmp/pytest-of-root is mode 700; add world-execute so the agent can traverse.
    for parent in [tmp_path, *tmp_path.parents]:
        if parent == Path("/"):
            break
        try:
            mode = parent.stat().st_mode
            os.chmod(parent, mode | 0o111)
        except OSError:
            pass
        if parent == Path("/tmp"):
            break
    try:
        os.chown(tmp_path, uid, gid)
        os.chmod(tmp_path, 0o755)
    except OSError:
        pass
