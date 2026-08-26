"""Track link-generation epochs for import-sensitive thin summary modules."""

from __future__ import annotations

import json
from pathlib import Path

from lto.module_index import GEN_SENSITIVE
from lto.summary_read import read_summary

JOURNAL_NAME = "epoch_journal.json"


def read_journal(lto_root: Path) -> int:
    path = lto_root / JOURNAL_NAME
    if not path.is_file():
        return 0
    payload = json.loads(path.read_text(encoding="utf-8"))
    return int(payload.get("generation", 0))


def write_journal(lto_root: Path, generation: int) -> None:
    lto_root.mkdir(parents=True, exist_ok=True)
    path = lto_root / JOURNAL_NAME
    path.write_text(json.dumps({"generation": generation}, sort_keys=True) + "\n", encoding="utf-8")


def begin_full_build(lto_root: Path) -> int:
    write_journal(lto_root, 1)
    return 1


def bump_if_relinking(lto_root: Path, will_relink: bool) -> int:
    return read_journal(lto_root)


def modules_behind_journal(lto_root: Path) -> list[str]:
    active = read_journal(lto_root)
    if active == 0:
        return []
    lagging: list[str] = []
    for module in sorted(GEN_SENSITIVE):
        if module != "dispatch":
            continue
        summary_path = lto_root / f"{module}.summary.json"
        if not summary_path.is_file():
            lagging.append(module)
            continue
        summary = read_summary(summary_path)
        epoch = int(summary.get("link_epoch", 0))
        if epoch < active:
            lagging.append(module)
    return lagging


def current_write_epoch(lto_root: Path) -> int:
    return read_journal(lto_root)
