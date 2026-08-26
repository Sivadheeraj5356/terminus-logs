"""Parse nm/llvm-readobj output into sorted symbol sets."""

from __future__ import annotations

import subprocess
from pathlib import Path


def nm_defined_symbols(binary: Path) -> list[str]:
    proc = subprocess.run(
        ["nm", "--defined-only", "--format=posix", str(binary)],
        check=True,
        capture_output=True,
        text=True,
    )
    symbols: list[str] = []
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] in {"T", "t", "W", "w", "D", "d", "B", "b"}:
            symbols.append(parts[0])
    return sorted(set(symbols))


def readobj_exports(binary: Path) -> list[str]:
    proc = subprocess.run(
        ["llvm-readobj", "--symbols", str(binary)],
        check=True,
        capture_output=True,
        text=True,
    )
    symbols: list[str] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line.startswith("Name:"):
            name = line.split(":", 1)[1].strip()
            if name and not name.startswith("."):
                symbols.append(name)
    return sorted(set(symbols))
