"""Check vtable dispatch behavior against probe stdout."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

_LINE_RE = re.compile(r"lane=(\d+) abi=(\S+) seed=(\d+) mixed=(\d+)")


def probe_values(binary: Path) -> dict[str, int | str]:
    proc = subprocess.run(
        [str(binary), "--probe"],
        check=True,
        capture_output=True,
        text=True,
    )
    match = _LINE_RE.search(proc.stdout)
    if not match:
        raise RuntimeError(f"unexpected probe output: {proc.stdout!r}")
    lane, abi, seed, mixed = match.groups()
    return {
        "lane": int(lane),
        "abi_tag": abi,
        "seed": int(seed),
        "mixed": int(mixed),
    }


def vtable_lane(binary: Path) -> int:
    return int(probe_values(binary)["lane"])
