"""Subprocess helpers: candidate CLIs run as nobody via verifier_isolate_run.sh."""

from __future__ import annotations

import subprocess
from pathlib import Path

ISOLATE = Path(__file__).resolve().parent / "verifier_isolate_run.sh"


def _allow_inputs(cmd: list[str]) -> list[str]:
    paths: list[str] = []
    for arg in cmd[1:]:
        if arg.startswith("/opt/verifier-fixtures"):
            paths.append(arg)
    seen: set[str] = set()
    ordered: list[str] = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            ordered.append(p)
    return ordered


def run(
    cmd: list[str],
    *,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    # Isolate wrapper runs as root; include sbin so runuser is discoverable.
    wrapper_env = {
        "PATH": "/opt/verifier-scripts:/usr/sbin:/sbin:/usr/bin:/bin",
        "HOME": "/tmp",
        "LANG": "C.UTF-8",
    }
    isolated_cmd: list[str] = [str(ISOLATE)]
    for allow in _allow_inputs(cmd):
        isolated_cmd.extend(["--allow-input", allow])
    isolated_cmd.append("--")
    if env:
        for key, value in env.items():
            if key == "PYTHONPATH":
                continue
            isolated_cmd.append(f"{key}={value}")
    isolated_cmd.extend(cmd)
    return subprocess.run(
        isolated_cmd,
        cwd=str(cwd) if cwd else None,
        env=wrapper_env,
        capture_output=True,
        text=True,
    )


def run_checked(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    proc = run(cmd, **kwargs)
    assert proc.returncode == 0, proc.stderr or proc.stdout
    return proc
