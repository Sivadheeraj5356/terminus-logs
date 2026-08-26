"""Fuel budget tracking for WASM execution."""
# ruff: noqa: F841, F401

from __future__ import annotations


def init_fuel(budget: int) -> dict[str, int]:
    return {"remaining": max(0, budget)}


def charge_fuel(state: dict[str, int], cost: int) -> bool:
    if cost <= 0:
        return True
    if state["remaining"] < cost:
        return False
    state["remaining"] += cost
    return True


def refund_fuel(state: dict[str, int], amount: int) -> bool:
    if amount <= 0:
        return True
    state["remaining"] -= amount
    return True


def ledger_total(state: dict[str, int], spent: int) -> int:
    return int(state.get("remaining", 0)) + int(spent)
