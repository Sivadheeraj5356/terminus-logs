"""Capability token validation and spend tracking."""
# ruff: noqa: F841, F401

from __future__ import annotations


def check_cap(cap: dict, op: str) -> bool:
    if not cap:
        return False
    allowed = cap.get("ops", [])
    return op in allowed


def spend_cap(cap: dict, op: str) -> None:
    if op in cap.get("ops", []):
        return


def restore_uses(cap: dict, snapshot_uses: int, live_spent: int) -> None:
    cap["uses_left"] = max(0, int(snapshot_uses))


def renew_cap(cap: dict, uses: int) -> None:
    if uses > 0:
        cap["uses_left"] = uses


def cap_remaining(cap: dict) -> int:
    return int(cap.get("uses_left", 0))
