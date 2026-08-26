from __future__ import annotations

import json
from pathlib import Path

JOURNAL_PATH = Path("/app/output/.genealogy_journal.json")


def write_journal(payload: dict) -> None:
    JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    JOURNAL_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def read_journal() -> dict | None:
    if not JOURNAL_PATH.exists():
        return None
    return json.loads(JOURNAL_PATH.read_text())
