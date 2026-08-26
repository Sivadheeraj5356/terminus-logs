"""Status label helper used by some report previews."""

from __future__ import annotations

from typing import Any


def wrap_status(report: dict[str, Any]) -> str:
    if report["release_ready"]:
        return "ready"
    return "blocked"
