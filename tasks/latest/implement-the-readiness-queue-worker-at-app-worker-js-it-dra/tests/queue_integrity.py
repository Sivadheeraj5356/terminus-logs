"""Verifier-owned queue envelope integrity checks."""

from __future__ import annotations

import json
from pathlib import Path

TRUSTED_PENDING = Path("/tests/data/pending")
APP_DONE = Path("/app/queue/done")
APP_SEED = Path("/app/queue/pending/.seed")


def trusted_envelopes() -> dict[str, dict]:
    envelopes: dict[str, dict] = {}
    for path in sorted(TRUSTED_PENDING.glob("*.json"), key=lambda p: p.name):
        envelopes[path.name] = json.loads(path.read_text())
    return envelopes


def verify_queue_envelopes_match_trusted() -> None:
    """Every done and seed envelope must exactly match verifier copies under /tests/data/pending."""
    for name, trusted in trusted_envelopes().items():
        done_path = APP_DONE / name
        seed_path = APP_SEED / name
        assert done_path.exists(), f"Missing done envelope {name}"
        assert seed_path.exists(), f"Missing seed envelope {name}"
        done = json.loads(done_path.read_text())
        seed = json.loads(seed_path.read_text())
        assert done == trusted, f"Done envelope {name} was modified"
        assert seed == trusted, f"Seed envelope {name} was modified"
