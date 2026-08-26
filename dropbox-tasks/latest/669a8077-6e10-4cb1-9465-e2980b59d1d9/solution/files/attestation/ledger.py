"""Release authorization continuity ledger."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from attestation.digest import ensure_parent

LEDGER_PATH = "/app/state/release-auth-ledger.json"


def load_ledger(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {
            "schema_version": 1,
            "last_batch_id": "",
            "last_digest": "",
            "evaluation_seq": 0,
        }
    return json.loads(path.read_text(encoding="utf-8"))


def bump_and_persist(path: Path, batch_id: str, digest: str) -> dict[str, Any]:
    ledger = load_ledger(path)
    ledger["schema_version"] = 1
    ledger["last_batch_id"] = batch_id
    ledger["last_digest"] = digest
    ledger["evaluation_seq"] = int(ledger.get("evaluation_seq", 0)) + 1
    ensure_parent(path)
    text = json.dumps(ledger, separators=(",", ":"))
    path.write_text(f"{text}\n", encoding="utf-8")
    return ledger
