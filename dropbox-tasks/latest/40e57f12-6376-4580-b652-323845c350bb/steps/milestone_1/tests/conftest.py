"""Apply variant seed to rotation-state before tests run."""

from __future__ import annotations

import json
import os
from pathlib import Path

ROTATION = Path("/app/auth/keys/rotation-state.json")


def pytest_configure() -> None:
    """Shift grace timing so fixes must read rotation-state.json, not service.toml."""
    seed = int(os.environ.get("TB_VARIANT_SEED", "1729"))
    state = json.loads(ROTATION.read_text(encoding="utf-8"))
    state["grace_seconds"] = 2400 + (seed % 900)
    state["rotated_at"] = int(state["rotated_at"]) + (seed % 401)
    ROTATION.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
