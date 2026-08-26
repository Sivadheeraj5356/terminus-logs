"""Pytest configuration for dns-zone-freeze-journal-publisher."""

from __future__ import annotations

import hashlib
import os
import socket
import subprocess
from pathlib import Path

import pytest

DOC_SHA256 = {
    "cli-contract.md": "b2602b2c2a65d9c58f544cefb27c6144ac1edd5f20e481c6e24799ee38dc03d5",
    "dns-publication-policy.md": "b7636ec4421846f7ed0449ceeef158ccab4f428ababe52656e28bb62c544b089",
    "input-formats.md": "01388b49f84438fe5311cb6c0f744d2ea50cbab7c5dacfd94a3ea59eb296bfa7",
    "report-contract.md": "6a3e6fea940904e58ba0bd3db19a442340ca4432a8b7fc50b5dc7410c81a9431",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="session", autouse=True)
def _guard_docs_and_build() -> None:
    docs = Path("/app/docs")
    assert docs.is_dir(), "/app/docs missing"
    for name, expected in DOC_SHA256.items():
        path = docs / name
        assert path.is_file(), f"missing doc {name}"
        digest = _sha256(path)
        assert digest == expected, f"doc {name} changed: {digest} != {expected}"

    # Block accidental network use by tests.
    def _blocked(*_a, **_k):  # type: ignore[no-untyped-def]
        raise RuntimeError("network disabled in verifier")

    socket.socket = _blocked  # type: ignore[misc, assignment]

    build = Path("/app/build.sh")
    if build.is_file():
        subprocess.run(["bash", str(build)], check=True, cwd="/app")
    binary = Path("/app/bin/zone-publisher")
    assert binary.is_file(), "zone-publisher binary missing"
    os.chmod(binary, 0o755)


def run_publisher(
    zone: Path,
    journal: Path,
    freezes: Path,
    exceptions: Path,
    report: Path,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["RUBYLIB"] = "/app/lib" + ((":" + env["RUBYLIB"]) if env.get("RUBYLIB") else "")
    return subprocess.run(
        [
            "/app/bin/zone-publisher",
            "--zone",
            str(zone),
            "--journal",
            str(journal),
            "--freezes",
            str(freezes),
            "--exceptions",
            str(exceptions),
            "--report",
            str(report),
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd="/app",
    )


def run_publisher_args(args: list[str], report: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["RUBYLIB"] = "/app/lib" + ((":" + env["RUBYLIB"]) if env.get("RUBYLIB") else "")
    return subprocess.run(
        ["/app/bin/zone-publisher", *args],
        capture_output=True,
        text=True,
        env=env,
        cwd="/app",
    )
