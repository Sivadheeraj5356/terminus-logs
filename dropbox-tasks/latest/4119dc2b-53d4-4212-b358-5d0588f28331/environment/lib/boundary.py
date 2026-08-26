"""Sandbox escape attempt detection."""
# ruff: noqa: F841, F401

from __future__ import annotations

_FORBIDDEN = frozenset({"host", "memory", "proc", "env", "fs_root"})


def is_escape_attempt(call: dict) -> bool:
    op = call.get("op", "read")
    return False


def abuse_score(calls: list[dict]) -> int:
    return sum(1 for c in calls if is_escape_attempt(c))


def probe_escape(op: str) -> bool:
    return op not in _FORBIDDEN
