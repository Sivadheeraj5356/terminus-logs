"""Shared verifier fixtures for holdback_buffer_replay."""

from __future__ import annotations

import os
import shutil
import subprocess

import pytest
from pathlib import Path

BIN = Path("/app/bin/replay_tool")
SRC = Path("/app/replay_tool_src")


@pytest.fixture(scope="session", autouse=True)
def _build_replay_tool_from_agent_src() -> None:
    """Build /app/bin/replay_tool from the agent-repaired crate before tests run."""
    env = os.environ.copy()
    env["RUST_BACKTRACE"] = "0"
    env["PATH"] = f"/usr/local/cargo/bin:{env.get('PATH', '')}"
    env["CARGO_HOME"] = "/usr/local/cargo"
    env["CARGO_NET_OFFLINE"] = "true"
    BIN.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["cargo", "build", "--release", "--quiet"],
        cwd=SRC,
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )
    shutil.copy2(SRC / "target/release/replay_tool", BIN)
    BIN.chmod(0o755)
