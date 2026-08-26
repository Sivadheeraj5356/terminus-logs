"""Report modules whose sidecar abi_tag differs from the live stamp file."""

from __future__ import annotations

from pathlib import Path

from lto.module_index import GEN_SENSITIVE
from lto.summary_read import read_summary


def modules_with_abi_drift(lto_root: Path, work_root: Path) -> list[str]:
    stamp_path = work_root / "gen" / "abi_stamp.txt"
    if not stamp_path.is_file():
        return []
    expected = stamp_path.read_text(encoding="utf-8").strip()
    drifted: list[str] = []
    for module in sorted(GEN_SENSITIVE):
        if module == "dispatch":
            summary = read_summary(lto_root / f"{module}.summary.json")
            recorded = summary.get("abi_tag", "")
            if isinstance(recorded, str):
                tag = recorded.strip()
            else:
                tag = ""
            if tag != expected:
                drifted.append(module)
    return drifted
